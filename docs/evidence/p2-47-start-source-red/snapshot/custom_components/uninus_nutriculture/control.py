"""Entry-owned refill execution; no scheduling or dosing."""

import asyncio
import time
import uuid
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED
from homeassistant.core import Context, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

from .control_auth import authorize
from .control_settings import resolve


class Controller:
    def __init__(self, tank):
        self.tank = tank
        self.hass = tank.hass
        self.master = False
        self.refill = False
        self.running = False
        self.flow_state = "uncommissioned"
        config = self.tank.entry.options.get("control", {})
        self._fault = config.get("fault")
        if config.get("commissioned"):
            try:
                target = resolve(self.hass, config.get("binding"))
                state = self.hass.states.get(target)
                if state is None or state.state != "off":
                    self.fault = "restart_output_not_off"
            except Exception:
                self.fault = "output_identity_invalid"
            self.flow_state = "fault" if self.fault else "disabled"
            if not self.fault:
                self.master = config.get("automation_enabled", False)
                self.refill = config.get("refill_enabled", False)
                if self.master:
                    self.flow_state = "idle"
        self.run_id = None
        self.lock = asyncio.Lock()
        self.target = None
        self.started = 0
        self.generation = 0
        self.receipts = {}
        self.on_task = None
        self.off_task = None
        self.late_on = False
        self.stop_context = None
        self.run_context = None
        self.tank.listeners.add(self.parameters_changed)
        self.unsub = self.hass.bus.async_listen(EVENT_STATE_CHANGED, self.changed)
        self.timer = async_track_time_interval(self.hass, self.tick, timedelta(seconds=1))
        self.registry_unsub = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self.registry_changed
        )
        self.shutdown_listener = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.shutdown
        )

    @property
    def fault(self):
        return self._fault

    @fault.setter
    def fault(self, value):
        self._fault = value
        options = self.tank.entry.options
        self.hass.config_entries.async_update_entry(
            self.tank.entry,
            options={
                **options,
                "control": {
                    **options.get("control", {}),
                    "fault": value,
                    "automation_enabled": False,
                },
            },
        )
        if value:
            self.master = False

    @callback
    def parameters_changed(self):
        if self.running and self.flow_state in ("starting", "refilling"):
            self.high_bound = min(self.high_bound, self.tank.parameters["level_high"])
            self.timeout_bound = min(
                self.timeout_bound, self.tank.parameters["refill_timeout"] * 60
            )
            self.hass.async_create_task(self.evaluate())

    @callback
    def registry_changed(self, event):
        self.tank.publish()
        if self.running:
            self.hass.async_create_task(self.evaluate())

    async def shutdown(self, event=None):
        self.tank.active = False
        self.master = False
        await self.stop()
        self.tank.listeners.discard(self.parameters_changed)
        self.unsub()
        self.registry_unsub()
        self.timer()
        if event is None:
            self.shutdown_listener()
        return not self.running

    @callback
    def tick(self, now):
        if self.running:
            self.hass.async_create_task(self.evaluate())

    @callback
    def changed(self, event):
        if self.running and event.data.get("entity_id") in (
            *self.tank.sources.values(),
            self.target,
        ):
            self.hass.async_create_task(self.evaluate())

    async def evaluate(self):
        if not self.running or self.flow_state != "refilling":
            return
        try:
            self.target = resolve(
                self.hass, self.tank.entry.options.get("control", {}).get("binding")
            )
        except Exception:
            self.fault = "output_identity_invalid"
        state = self.hass.states.get(self.target)
        if self.tank.snapshot()[0] == "invalid":
            self.fault = "source_invalid"
        elif state is None or state.state != "on":
            self.fault = "output_unexpected"
        elif time.monotonic() - self.started >= self.timeout_bound:
            self.fault = "refill_timeout"
        if self.fault:
            await self.stop("fault")
        elif float(self.hass.states.get(self.tank.sources["level"]).state) >= self.high_bound:
            await self.stop("completed")

    async def action(self, key, enabled, context, *, guard=None):
        await authorize(self.hass, context)
        if guard is not None:
            guard()
        from homeassistant.exceptions import ServiceValidationError

        if not self.tank.active or key not in ("automation_enabled", "refill_enabled", "flow_run"):
            raise ServiceValidationError("inactive_control")
        if enabled and key != "flow_run":
            if self.fault:
                raise ServiceValidationError("fault_latched")
            config = self.tank.entry.options.get("control", {})
            if not config.get("commissioned"):
                raise ServiceValidationError("uncommissioned")
            resolve(self.hass, config.get("binding"))
        if key == "automation_enabled":
            self.master = enabled
        elif key == "refill_enabled":
            self.refill = enabled
        elif key == "flow_run":
            if enabled:
                return await self.start(context, guard=guard)
            await self.stop(context=context)
        if key in ("automation_enabled", "refill_enabled"):
            options = self.tank.entry.options
            self.hass.config_entries.async_update_entry(
                self.tank.entry,
                options={**options, "control": {**options.get("control", {}), key: enabled}},
            )
            if not enabled:
                await self.stop(context=context)
            if not self.running and not self.fault:
                self.flow_state = "idle" if self.master else "disabled"
        self.tank.publish()

    async def press(self, key, context, *, guard=None):
        from homeassistant.exceptions import ServiceValidationError

        await authorize(self.hass, context)
        if guard is not None:
            guard()
        if key == "emergency_stop":
            self.fault = "emergency_stop"
            self.master = False
            config = self.tank.entry.options.get("control", {})
            if config.get("commissioned") and not self.running:
                self.target = resolve(self.hass, config.get("binding"))
                output = self.hass.states.get(self.target)
                self.running = output is None or output.state != "off"
            await self.stop("fault", context=context)
            self.flow_state = "fault"
        elif key == "reset_fault":
            target = resolve(self.hass, self.tank.entry.options.get("control", {}).get("binding"))
            state = self.hass.states.get(target)
            if (
                self.running
                or state is None
                or state.state != "off"
                or self.tank.snapshot()[0] == "invalid"
            ):
                raise ServiceValidationError("reset_unsafe")
            self.fault = None
            self.master = False
            self.flow_state = "disabled"
        self.tank.publish()

    async def start(self, context, *, request_id=None, service=False, guard=None):
        from homeassistant.exceptions import ServiceValidationError

        generation = self.generation
        stopping_at_request = self.flow_state in ("stopping", "fault") and self.running
        await authorize(self.hass, context)
        if stopping_at_request:
            raise ServiceValidationError("busy")
        if guard is not None:
            guard()
        async with self.lock:
            await authorize(self.hass, context)
            if guard is not None:
                guard()
            if generation != self.generation or not self.tank.active:
                raise ServiceValidationError("revoked")
            self.receipts = {
                key: value
                for key, value in self.receipts.items()
                if time.monotonic() - value[0] < 86400
            }
            if request_id in self.receipts:
                return dict(self.receipts[request_id][1])
            if not self.master or not self.refill:
                raise ServiceValidationError("disabled")
            if self.running:
                if service or self.flow_state != "refilling":
                    raise ServiceValidationError("busy")
                return {"accepted": True, "run_id": self.run_id}
            from homeassistant.util import dt as dt_util

            from .control_settings import DAYS

            config = self.tank.entry.options.get("control", {})
            if not config.get("commissioned"):
                raise ServiceValidationError("uncommissioned")
            self.target = resolve(self.hass, config.get("binding"))
            if self.tank.snapshot()[0] == "invalid":
                raise ServiceValidationError("source_invalid")
            if (
                float(self.hass.states.get(self.tank.sources["level"]).state)
                >= self.tank.parameters["level_low"]
            ):
                raise ServiceValidationError("level_not_low")
            output = self.hass.states.get(self.target)
            if output is None or output.state != "off":
                raise ServiceValidationError("output_not_off")
            if DAYS[dt_util.now().weekday()] not in config.get("allowed_weekdays", {}).get(
                "refill", DAYS
            ):
                raise ServiceValidationError("weekday")
            self.high_bound = self.tank.parameters["level_high"]
            self.timeout_bound = self.tank.parameters["refill_timeout"] * 60
            self.started = time.monotonic()
            self.stop_context = None
            self.run_context = context
            self.run_id = uuid.uuid4().hex
            self.running = True
            self.flow_state = "starting"
            try:
                async with asyncio.timeout(config.get("feedback_timeout", 10)):
                    self.on_task = self.hass.async_create_task(
                        self.hass.services.async_call(
                            "switch",
                            "turn_on",
                            {"entity_id": self.target},
                            blocking=True,
                            context=context,
                        )
                    )
                    self.on_task.add_done_callback(self.on_settled)
                    await asyncio.shield(self.on_task)
                    while (
                        output := self.hass.states.get(self.target)
                    ) is None or output.state != "on":
                        await asyncio.sleep(0.02)
                    await authorize(self.hass, context)
                    if guard is not None:
                        guard()
                    if time.monotonic() - self.started >= self.timeout_bound:
                        self.fault = "refill_timeout"
                        raise ServiceValidationError("refill_timeout")
                    if (
                        generation != self.generation
                        or not self.tank.active
                        or not self.master
                        or not self.refill
                        or self.tank.snapshot()[0] == "invalid"
                        or self.fault
                        or config != self.tank.entry.options.get("control", {})
                    ):
                        raise ServiceValidationError("revoked")
            except asyncio.CancelledError:
                self.fault = "start_cancelled"
                cleanup = asyncio.create_task(self._stop_locked("fault", context=context))
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        continue
                cleanup.result()
                raise
            except Exception as err:
                self.fault = self.fault or "start_unconfirmed"
                await self._stop_locked("fault", context=context)
                raise ServiceValidationError("start_unconfirmed") from err
            self.flow_state = "refilling"
            receipt = {"accepted": True, "run_id": self.run_id}
            if request_id is not None:
                self.receipts[request_id] = (time.monotonic(), receipt)
                while len(self.receipts) > 64:
                    self.receipts.pop(next(iter(self.receipts)))
            self.tank.publish()
            return dict(receipt)

    @callback
    def on_settled(self, task):
        if not task.cancelled():
            task.exception()
        if self.late_on:
            self.late_on = False
            self.hass.async_create_task(self.stop("fault"))

    @callback
    def off_settled(self, task):
        if not task.cancelled():
            task.exception()
        # A late OFF completion may establish stopped truth, never clear the fault.
        if self.flow_state == "fault" and not (self.on_task and not self.on_task.done()):
            try:
                target = resolve(
                    self.hass, self.tank.entry.options.get("control", {}).get("binding")
                )
            except Exception:
                return
            output = self.hass.states.get(target)
            if output and output.state == "off":
                self.running = False
                self.tank.publish()

    async def stop(self, state="aborted", *, context=None):
        if context is not None:
            self.stop_context = context
        self.generation += 1
        async with self.lock:
            cleanup = asyncio.create_task(self._stop_locked(state, context=context))
            cancelled = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cancelled = True
            cleanup.result()
            if cancelled:
                raise asyncio.CancelledError

    async def _stop_locked(self, state, *, context=None):
        if self.running:
            self.flow_state = "stopping"
            self.late_on = self.on_task is not None and not self.on_task.done()
            timeout = self.tank.entry.options.get("control", {}).get("feedback_timeout", 10)
            try:
                async with asyncio.timeout(timeout):
                    origin = self.stop_context or context or self.run_context
                    self.target = resolve(
                        self.hass, self.tank.entry.options.get("control", {}).get("binding")
                    )
                    if self.off_task is None or self.off_task.done():
                        self.off_task = self.hass.async_create_task(
                            self.hass.services.async_call(
                                "switch",
                                "turn_off",
                                {"entity_id": self.target},
                                blocking=True,
                                # Internal safety authority retains the initiating trace.
                                context=Context(parent_id=origin.id)
                                if origin is not None
                                else Context(),
                            )
                        )
                        self.off_task.add_done_callback(self.off_settled)
                    await asyncio.shield(self.off_task)
                    while (
                        output := self.hass.states.get(self.target)
                    ) is None or output.state != "off":
                        await asyncio.sleep(0.02)
            except TimeoutError, Exception:
                self.fault = "stop_unconfirmed"
                self.flow_state = "fault"
            else:
                pending_on = self.on_task is not None and not self.on_task.done()
                self.running = pending_on
                self.flow_state = "fault" if self.fault or pending_on else state
            self.tank.publish()
