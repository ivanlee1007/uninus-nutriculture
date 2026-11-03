"""Entry-owned refill execution; no scheduling or dosing."""
import asyncio
import uuid
import time
from datetime import timedelta

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED
from homeassistant.core import callback

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
        self.fault = None
        self.run_id = None
        self.lock = asyncio.Lock()
        self.target = None
        self.started = 0
        self.unsub = self.hass.bus.async_listen(EVENT_STATE_CHANGED, self.changed)
        self.timer = async_track_time_interval(self.hass, self.tick, timedelta(seconds=1))
        self.shutdown_listener = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)

    async def shutdown(self, event=None):
        self.tank.active = False
        self.master = False
        await self.stop()
        self.unsub()
        self.timer()
        self.shutdown_listener()
        return not self.running

    @callback
    def tick(self, now):
        if self.running:
            self.hass.async_create_task(self.evaluate())

    @callback
    def changed(self, event):
        if self.running and event.data.get("entity_id") in (*self.tank.sources.values(), self.target):
            self.hass.async_create_task(self.evaluate())

    async def evaluate(self):
        if not self.running or self.flow_state != "refilling":
            return
        state = self.hass.states.get(self.target)
        if self.tank.snapshot()[0] == "invalid":
            self.fault = "source_invalid"
        elif state is None or state.state != "on":
            self.fault = "output_unexpected"
        elif time.monotonic() - self.started >= self.tank.parameters["refill_timeout"] * 60:
            self.fault = "refill_timeout"
        if self.fault:
            await self.stop("fault")
        elif float(self.hass.states.get(self.tank.sources["level"]).state) >= self.tank.parameters["level_high"]:
            await self.stop("completed")

    async def action(self, key, enabled, context):
        await authorize(self.hass, context)
        if key == "automation_enabled":
            self.master = enabled
        elif key == "refill_enabled":
            self.refill = enabled
        elif key == "flow_run":
            if enabled:
                return await self.start(context)
            await self.stop()
        if key in ("automation_enabled", "refill_enabled") and not enabled:
            await self.stop()
        self.tank.publish()

    async def press(self, key, context):
        from homeassistant.exceptions import ServiceValidationError
        await authorize(self.hass, context)
        if key == "emergency_stop":
            self.fault = "emergency_stop"
            self.master = False
            await self.stop("fault")
            self.flow_state = "fault"
        elif key == "reset_fault":
            target = resolve(self.hass, self.tank.entry.options.get("control", {}).get("binding"))
            state = self.hass.states.get(target)
            if self.running or state is None or state.state != "off" or self.tank.snapshot()[0] == "invalid":
                raise ServiceValidationError("reset_unsafe")
            self.fault = None
            self.master = False
            self.flow_state = "disabled"
        self.tank.publish()

    async def start(self, context):
        from homeassistant.exceptions import ServiceValidationError
        await authorize(self.hass, context)
        async with self.lock:
            await authorize(self.hass, context)
            if not self.master or not self.refill:
                raise ServiceValidationError("disabled")
            if self.running:
                return
            from homeassistant.util import dt as dt_util
            from .control_settings import DAYS
            config = self.tank.entry.options.get("control", {})
            if not config.get("commissioned"):
                raise ServiceValidationError("uncommissioned")
            self.target = resolve(self.hass, config.get("binding"))
            if self.tank.snapshot()[0] == "invalid":
                raise ServiceValidationError("source_invalid")
            if float(self.hass.states.get(self.tank.sources["level"]).state) >= self.tank.parameters["level_low"]:
                raise ServiceValidationError("level_not_low")
            output = self.hass.states.get(self.target)
            if output is None or output.state != "off":
                raise ServiceValidationError("output_not_off")
            if DAYS[dt_util.now().weekday()] not in config.get("allowed_weekdays", {}).get("refill", DAYS):
                raise ServiceValidationError("weekday")
            self.started = time.monotonic()
            self.run_id = uuid.uuid4().hex
            self.running = True
            self.flow_state = "refilling"
            await self.hass.services.async_call("switch", "turn_on", {"entity_id": self.target}, blocking=True, context=context)
            self.tank.publish()

    async def stop(self, state="aborted"):
        async with self.lock:
            if self.running:
                self.flow_state = "stopping"
                timeout = self.tank.entry.options.get("control", {}).get("feedback_timeout", 10)
                try:
                    async with asyncio.timeout(timeout):
                        await self.hass.services.async_call("switch", "turn_off", {"entity_id": self.target}, blocking=True)
                        while (output := self.hass.states.get(self.target)) is None or output.state != "off":
                            await asyncio.sleep(0.02)
                except (TimeoutError, Exception):
                    self.fault = "stop_unconfirmed"
                    self.flow_state = "fault"
                else:
                    self.running = False
                    self.flow_state = "fault" if self.fault else state
                self.tank.publish()
