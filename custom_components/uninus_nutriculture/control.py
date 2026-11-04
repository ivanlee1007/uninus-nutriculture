"""Entry-owned refill execution; no scheduling or dosing."""

import asyncio
import time
import uuid
from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED, EVENT_STATE_REPORTED
from homeassistant.core import Context, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

from .control_auth import authorize
from .control_settings import resolve

# Exact closed codes only: provider exceptions (including ServiceValidationError)
# are not a trusted source of persistent/public diagnostics. None alone clears.
_FAULT_CODES = frozenset(
    {
        "circulation_lost",
        "dose_budget_exhausted",
        "ec_danger",
        "ec_timeout",
        "ph_timeout",
        "emergency_stop",
        "flow_timeout",
        "level_unsafe",
        "operation_failed",
        "output_already_owned",
        "output_identity_invalid",
        "output_not_off",
        "output_unbound",
        "output_unexpected",
        "ph_danger",
        "refill_timeout",
        "restart_output_not_off",
        "revoked",
        "sample_invalid",
        "sample_timeout",
        "source_invalid",
        "start_cancelled",
        "start_unconfirmed",
        "stop_unconfirmed",
        "weekday",
    }
)


def _fault_code(value):
    if value is None:
        return None
    return value if type(value) is str and value in _FAULT_CODES else "operation_failed"


class Controller:
    def __init__(self, tank):
        self.tank = tank
        self.hass = tank.hass
        self.master = False
        self.refill = False
        self.running = False
        self.flow_state = "uncommissioned"
        config = self.tank.entry.options.get("control", {})
        self._fault = None
        if config.get("fault") is not None:
            # Re-open legacy latched faults through the same closed boundary;
            # never publish old arbitrary persisted diagnostics after restart.
            self.fault = config["fault"]
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
        self.nutrient = config.get("nutrient_enabled", False)
        if config.get("nutrient_commissioned"):
            try:
                for role in ("nutrient", "circulation"):
                    output = self.hass.states.get(resolve(self.hass, config.get(role + "_binding")))
                    if output is None or output.state != "off":
                        self.fault = "restart_output_not_off"
            except Exception:
                self.fault = "output_identity_invalid"
            self.master = False if self.fault else config.get("automation_enabled", False)
            self.flow_state = "fault" if self.fault else "idle" if self.master else "disabled"
        from .nutrient import NutrientStage

        if config.get("acid_commissioned"):
            try:
                for role in ("acid", "circulation"):
                    output = self.hass.states.get(resolve(self.hass, config.get(role + "_binding")))
                    if output is None or output.state != "off":
                        self.fault = "restart_output_not_off"
            except Exception:
                self.fault = "output_identity_invalid"
            self.master = False if self.fault else config.get("automation_enabled", False)
            self.flow_state = "fault" if self.fault else "idle" if self.master else "disabled"
        self.nutrient_stage = NutrientStage(self)
        self.acid_stage = NutrientStage(self, "acid")
        self.acid = config.get("acid_enabled", False)
        from .mix import MixStage

        self.mix_stage = MixStage(self)
        self.mix = config.get("mix_enabled", False)
        self.leases = {}
        from .flow import FlowCoordinator

        self.flow = FlowCoordinator(self)
        self.ph_high_since = None
        self.ph_high_alarm_active = False
        self.run_id = None
        self.run_stage = None
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
        self.report_unsub = self.hass.bus.async_listen(
            EVENT_STATE_REPORTED, self.changed, event_filter=self.report_filter
        )
        self.timer = async_track_time_interval(self.hass, self.tick, timedelta(seconds=1))
        self.registry_unsub = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self.registry_changed
        )
        self.shutdown_listener = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.shutdown
        )

    @property
    def flow_state(self):
        flow = getattr(self, "flow", None)
        return flow.state if flow and flow.run_plan else self._flow_state

    @flow_state.setter
    def flow_state(self, value):
        self._flow_state = value

    @property
    def running(self):
        return (
            bool(getattr(self, "flow", None) and self.flow.pending)
            or self._refill_running
            or any(
                getattr(self, key, None) and getattr(self, key).owns_io
                for key in ("nutrient_stage", "acid_stage", "mix_stage")
            )
        )

    @running.setter
    def running(self, value):
        # P2 owns this flag. Nutrient I/O has its own retained ownership record.
        self._refill_running = value

    @property
    def execution_stage(self):
        return getattr(
            self, (getattr(self, "run_stage", None) or "nutrient") + "_stage", self.nutrient_stage
        )

    @property
    def supports_mix(self):
        return bool(self.tank.entry.options.get("control", {}).get("mix_commissioned"))

    def acquire(self, identity, run_id, generation, owner):
        from homeassistant.exceptions import ServiceValidationError

        if generation != self.generation or (
            self.leases and any(v[0] != identity for v in self.leases.values())
        ):
            raise ServiceValidationError("revoked")
        token = uuid.uuid4().hex
        self.leases[token] = (identity, run_id, generation, owner)
        return token

    def release(self, token):
        self.leases.pop(token, None)
        return not self.leases

    @property
    def supports_acid(self):
        return bool(self.tank.entry.options.get("control", {}).get("acid_commissioned"))

    @property
    def supports_nutrient(self):
        return bool(self.tank.entry.options.get("control", {}).get("nutrient_commissioned"))

    @property
    def nutrient_phase(self):
        return self.execution_stage.phase

    @property
    def dose_progress(self):
        return self.execution_stage.progress

    async def nutrient_revalidate(self, *, stage=None):
        from homeassistant.exceptions import ServiceValidationError

        stage = stage or self.execution_stage
        await authorize(self.hass, self.run_context)
        if stage.guard:
            stage.guard()
        if (
            not self.tank.active
            or self.tank.entry.runtime_data is not self.tank
            or stage.generation != self.generation
            or not self.master
            or not getattr(self, stage.role)
            or self.fault
            or self.tank.sources != stage.sources
        ):
            raise ServiceValidationError("revoked")
        stage.validate()
        config = self.tank.entry.options.get("control", {})
        for owned_role, binding in stage.bindings.items():
            if config.get(owned_role + "_binding") != binding:
                raise ServiceValidationError("output_identity_invalid")
            stage.targets[owned_role] = resolve(self.hass, binding)

    async def nutrient_dispatch(self, role, enabled, *, stage=None):
        from homeassistant.exceptions import ServiceValidationError
        from homeassistant.util import dt as dt_util

        from .control_settings import DAYS

        # NutrientStage's legacy no-stage dispatch is the nutrient owner,
        # never the currently selected acid/mix execution stage.
        stage = stage or self.nutrient_stage
        if enabled:
            await self.nutrient_revalidate(stage=stage)
            config = self.tank.entry.options.get("control", {})
            if role == "circulation" and not stage.circulation_confirmed:
                days = (
                    self.flow.run_plan["allowed_weekdays"]
                    if self.flow.active
                    else config.get("allowed_weekdays", {})
                )
                day = self.flow.weekday() if self.flow.active else DAYS[dt_util.now().weekday()]
                if day not in days.get(stage.role, DAYS):
                    raise ServiceValidationError("weekday")
            if role == stage.role and role != "mix":
                circ = self.hass.states.get(stage.targets["circulation"])
                if not stage.circulation_confirmed or circ is None or circ.state != "on":
                    raise ServiceValidationError("circulation_lost")
        if self.flow.active and role == "circulation":
            async with self.flow.circ_lock:
                target = resolve(self.hass, stage.bindings[role])
                stage.targets[role] = target
                if enabled:
                    now = time.monotonic()
                    config = self.tank.entry.options["control"]
                    if self.flow.circ_start is None:
                        self.flow.circ_start = now
                        self.flow.circ_cutoff = (
                            now
                            + config["circulation_device_max_on_seconds"]
                            - config.get("feedback_timeout", 10)
                        )
                    if now >= self.flow.circ_cutoff:
                        raise ServiceValidationError("flow_timeout")
                    stage.circ_physical_cutoff = self.flow.circ_cutoff
                    had_owners = bool(self.leases)
                    if not getattr(stage, "lease", None):
                        stage.lease = self.acquire(
                            stage.bindings[role], self.run_id, stage.generation, stage.role
                        )
                    self.flow.dispatched(stage.role)
                    state = self.hass.states.get(target)
                    if had_owners and state and state.state == "on":
                        return
                else:
                    if getattr(stage, "lease", None):
                        last = self.release(stage.lease)
                        stage.lease = None
                        if not last:
                            return
                    elif self.leases:
                        return
            origin = self.stop_context or self.run_context
            await self.hass.services.async_call(
                "switch",
                "turn_on" if enabled else "turn_off",
                {"entity_id": target},
                blocking=True,
                context=origin
                if enabled
                else Context(parent_id=origin.id)
                if origin
                else Context(),
            )
            if (
                not enabled
                and not self.leases
                and not any(
                    not task.done()
                    for owner in (self.nutrient_stage, self.acid_stage, self.mix_stage)
                    for (r, on), task in owner.operations.items()
                    if r == "circulation" and on
                )
            ):
                self.flow.circ_start = self.flow.circ_cutoff = None
            return
        if role == "circulation":
            if enabled and not getattr(stage, "lease", None):
                stage.lease = self.acquire(
                    stage.bindings[role],
                    self.run_id,
                    stage.generation,
                    "standalone_mix" if stage.role == "mix" else stage.role + "_required",
                )
            if not enabled and getattr(stage, "lease", None):
                if not self.release(stage.lease):
                    return
                stage.lease = None
        target = resolve(self.hass, stage.bindings[role])
        stage.targets[role] = target
        origin = self.stop_context or self.run_context
        context = origin if enabled else Context(parent_id=origin.id) if origin else Context()
        await self.hass.services.async_call(
            "switch",
            "turn_on" if enabled else "turn_off",
            {"entity_id": target},
            blocking=True,
            context=context,
        )
        if enabled:
            await self.nutrient_revalidate(stage=stage)

    async def flow_refill_dispatch(self, stage, enabled):
        from homeassistant.exceptions import ServiceValidationError

        if enabled:
            await authorize(self.hass, self.run_context)
            if (
                not self.flow.active
                or self.flow.generation != self.generation
                or not self.master
                or self.fault
                or not self.refill
            ):
                raise ServiceValidationError("revoked")
            from .flow_settings import source

            if any(source(self.tank, k) is None for k in ("level", "ph", "ec")):
                raise ServiceValidationError("source_invalid")
        target = resolve(self.hass, stage.binding)
        if enabled:
            self.flow.dispatched("refill")
        origin = self.stop_context or self.run_context
        await self.hass.services.async_call(
            "switch",
            "turn_on" if enabled else "turn_off",
            {"entity_id": target},
            blocking=True,
            context=origin if enabled else Context(parent_id=origin.id) if origin else Context(),
        )

    @property
    def fault(self):
        return self._fault

    @fault.setter
    def fault(self, value):
        value = _fault_code(value)
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
        self.update_ph_alarm()
        if self.flow.active:
            self.flow.tighten()
            for stage in (self.nutrient_stage, self.acid_stage, self.mix_stage):
                if stage.owns_io:
                    stage.tighten()
            return
        if self.execution_stage.owns_io:
            self.execution_stage.tighten()
        if (
            self.running
            and not (self.execution_stage.task and not self.execution_stage.task.done())
            and self.flow_state in ("starting", "refilling")
        ):
            self.high_bound = min(self.high_bound, self.tank.parameters["level_high"])
            self.timeout_bound = min(
                self.timeout_bound, self.tank.parameters["refill_timeout"] * 60
            )
            self.hass.async_create_task(self.evaluate())

    @callback
    def registry_changed(self, event):
        if self.flow.active:
            for stage in (self.nutrient_stage, self.acid_stage, self.mix_stage):
                if stage.owns_io:
                    try:
                        for binding in stage.bindings.values():
                            resolve(self.hass, binding)
                    except Exception:
                        stage.revoked = "output_identity_invalid"
                        stage.wake.set()
            self.tank.publish()
            return
        stage = self.execution_stage
        if stage.owns_io:
            try:
                config = self.tank.entry.options.get("control", {})
                for role, binding in stage.bindings.items():
                    if config.get(role + "_binding") != binding:
                        raise ValueError("binding_changed")
                    stage.targets[role] = resolve(self.hass, binding)
            except Exception:
                stage.revoked = stage.revoked or "output_identity_invalid"
                stage.wake.set()
        self.tank.publish()
        if self.running:
            self.hass.async_create_task(self.evaluate())

    async def shutdown(self, event=None):
        self.tank.active = False
        self.master = False
        await self.stop()
        self.tank.listeners.discard(self.parameters_changed)
        self.unsub()
        self.report_unsub()
        self.registry_unsub()
        self.timer()
        if event is None:
            self.shutdown_listener()
        return not self.running

    @callback
    def tick(self, now):
        self.update_ph_alarm()
        if self.running:
            self.hass.async_create_task(self.evaluate())

    @callback
    def update_ph_alarm(self, event=None):
        import math

        from homeassistant.util import dt as dt_util

        previous = self.ph_high_alarm_active
        state = (
            event.data.get("new_state")
            if event is not None
            else self.hass.states.get(self.tank.sources["ph"])
        )
        options = self.tank.entry.options
        settings = options.get(
            "safety_parameters"
            if options.get("control_contract_version") in (4, 5)
            else "dosing_parameters",
            {},
        )
        try:
            value = float(state.state)
            valid = (
                (self.supports_nutrient or self.supports_acid or self.supports_mix)
                and self.tank.active
                and math.isfinite(value)
                and state.attributes.get("unit_of_measurement") in (None, "", "pH")
                and 0
                <= (dt_util.utcnow() - state.last_reported).total_seconds()
                <= self.tank.entry.options.get("max_age_seconds", 300)
            )
        except AttributeError, TypeError, ValueError:
            valid = False
        if not valid or value <= settings.get("ph_high_alarm", 6.8):
            self.ph_high_since = None
            self.ph_high_alarm_active = False
        else:
            now = self.execution_stage.clock()
            if self.ph_high_since is None:
                self.ph_high_since = now
            self.ph_high_alarm_active = now - self.ph_high_since >= settings.get(
                "ph_high_alarm_seconds", 600
            )
        if previous != self.ph_high_alarm_active:
            self.tank.publish()

    @callback
    def report_filter(self, data):
        return data.get("entity_id") in self.tank.sources.values()

    @callback
    def changed(self, event):
        if event.data.get("entity_id") == self.tank.sources["ph"]:
            self.update_ph_alarm(event)
        if self.flow.active:
            for name in ("refill", "nutrient", "acid", "mix"):
                stage = self.flow.stage(name)
                if stage.owns_io:
                    self.flow.changed(name, event)
                    stage.changed(event)
            self.tank.publish()
            return
        if self.running and self.execution_stage.task and not self.execution_stage.task.done():
            self.execution_stage.changed(event)
            return
        if self.running and event.data.get("entity_id") in (
            *self.tank.sources.values(),
            self.target,
        ):
            self.hass.async_create_task(self.evaluate())

    async def evaluate(self):
        if self.flow.active:
            for stage in (self.nutrient_stage, self.acid_stage, self.mix_stage):
                if stage.owns_io:
                    stage.wake.set()
            return
        if self.execution_stage.owns_io:
            self.execution_stage.wake.set()
            return
        if self.running and self.flow_state == "starting":
            # Revoke observed source loss even if it recovers before ON returns.
            # Output OFF is still legitimate while acknowledgement is pending.
            if self.tank.snapshot()[0] == "invalid":
                self.fault = "source_invalid"
                await self.stop("fault")
            return
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

        if self.tank.entry.options.get("control_contract_version", 3) not in (3, 4, 5):
            raise ServiceValidationError("settings_schema_mismatch")
        if not self.tank.active or key not in (
            "automation_enabled",
            "refill_enabled",
            "nutrient_enabled",
            "acid_enabled",
            "mix_enabled",
            "flow_run",
        ):
            raise ServiceValidationError("inactive_control")
        owned_nutrient = self.execution_stage.owns_io
        if enabled and key != "flow_run":
            if self.fault:
                raise ServiceValidationError("fault_latched")
            config = self.tank.entry.options.get("control", {})
            if key == "mix_enabled" or (key == "automation_enabled" and self.supports_mix):
                if not self.supports_mix:
                    raise ServiceValidationError("uncommissioned")
                resolve(self.hass, config.get("circulation_binding"))
            elif key == "acid_enabled" or (key == "automation_enabled" and self.supports_acid):
                if not self.supports_acid:
                    raise ServiceValidationError("uncommissioned")
                for role in ("acid", "circulation"):
                    resolve(self.hass, config.get(role + "_binding"))
            elif key == "nutrient_enabled" or (
                key == "automation_enabled" and self.supports_nutrient
            ):
                if not self.supports_nutrient:
                    raise ServiceValidationError("uncommissioned")
                for role in ("nutrient", "circulation"):
                    resolve(self.hass, config.get(role + "_binding"))
            else:
                if not config.get("commissioned"):
                    raise ServiceValidationError("uncommissioned")
                resolve(self.hass, config.get("binding"))
        if key == "automation_enabled":
            self.master = enabled
        elif key == "refill_enabled":
            self.refill = enabled
        elif key == "mix_enabled":
            self.mix = enabled
        elif key == "acid_enabled":
            self.acid = enabled
        elif key == "nutrient_enabled":
            self.nutrient = enabled
        elif key == "flow_run":
            if enabled:
                return await self.start(context, guard=guard)
            await self.stop(context=context)
        if key in (
            "automation_enabled",
            "refill_enabled",
            "nutrient_enabled",
            "acid_enabled",
            "mix_enabled",
        ):
            options = self.tank.entry.options
            self.hass.config_entries.async_update_entry(
                self.tank.entry,
                options={**options, "control": {**options.get("control", {}), key: enabled}},
            )
            if self.flow.active:
                name = key.removesuffix("_enabled")
                if not enabled and (
                    key == "automation_enabled"
                    or (name in self.flow.times and self.flow.stage(name).owns_io)
                ):
                    await self.stop(context=context)
                self.tank.publish()
                return
            if not enabled and (
                key == "automation_enabled"
                or (
                    key == (self.run_stage or "") + "_enabled"
                    and self.execution_stage.task
                    and not self.execution_stage.task.done()
                )
                or (key == "refill_enabled" and not self.nutrient)
            ):
                await self.stop(context=context)
            if not self.running and not self.fault and not owned_nutrient:
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
            for name in ("acid", "mix"):
                stage = getattr(self, name + "_stage")
                if getattr(self, "supports_" + name) and not stage.owns_io:
                    roles = ("acid", "circulation") if name == "acid" else ("circulation",)
                    stage.bindings = {role: dict(config[role + "_binding"]) for role in roles}
                    # Capture responsibility before resolving any identity.
                    # Each output resolves independently in the existing dispatcher;
                    # an invalid role must not strand another commissioned owner.
                    stage.targets = {}
                    stage.operations = {}
                    stage.owns_io = True
                    # Arm every commissioned owner before awaiting any ACK.
                    # stop() joins all owners concurrently, including refill.
            if self.supports_nutrient and not self.nutrient_stage.owns_io:
                # Emergency owns the commissioned nutrient role independently
                # of the active acid/mix stage and separate P2 pending-I/O flag.
                stage = self.nutrient_stage
                stage.bindings = {
                    role: dict(config[role + "_binding"]) for role in ("nutrient", "circulation")
                }
                stage.operations = {}
                stage.owns_io = True
            if config.get("commissioned") and not self._refill_running:
                try:
                    self.target = resolve(self.hass, config.get("binding"))
                    output = self.hass.states.get(self.target)
                    self.running = output is None or output.state != "off"
                except Exception:
                    self.running = True  # Unknown identity cannot establish OFF.
            await self.stop("fault", context=context)
            self.flow_state = "fault"
        elif key == "reset_fault":
            config = self.tank.entry.options.get("control", {})
            bindings = [config.get("binding")] if config.get("commissioned") else []
            if self.supports_nutrient:
                bindings.extend(
                    config.get(role + "_binding") for role in ("nutrient", "circulation")
                )
            if self.supports_acid:
                bindings.extend(config.get(role + "_binding") for role in ("acid", "circulation"))
            if self.supports_mix:
                bindings.append(config.get("circulation_binding"))
            level_only = self.supports_mix and not (
                self.supports_nutrient or self.supports_acid or config.get("commissioned")
            )
            if level_only:
                self.mix_stage.validate_sources(reset=True)
            states = [self.hass.states.get(resolve(self.hass, binding)) for binding in bindings]
            if (
                not states
                or self.running
                or any(state is None or state.state != "off" for state in states)
                or (not level_only and self.tank.snapshot()[0] == "invalid")
            ):
                raise ServiceValidationError("reset_unsafe")
            if self.supports_nutrient and any(
                self.execution_stage.unsafe(
                    key,
                    float(self.hass.states.get(entity_id).state),
                    settings=self.tank.entry.options["dosing_parameters"],
                )
                for key, entity_id in self.tank.sources.items()
            ):
                raise ServiceValidationError("reset_unsafe")
            if self.supports_acid:
                for key, entity_id in self.tank.sources.items():
                    if self.acid_stage.unsafe(
                        key,
                        float(self.hass.states.get(entity_id).state),
                        settings=self.acid_stage.live_settings(),
                    ):
                        raise ServiceValidationError("reset_unsafe")
            self.fault = None
            if self.flow.run_plan:
                self.flow.outcome = None
            self.acid_stage.revoked = None
            self.mix_stage.revoked = None
            self.execution_stage.revoked = None
            self.master = False
            self.flow_state = "disabled"
        self.tank.publish()

    async def start(self, context, *, request_id=None, service=False, guard=None):
        from homeassistant.exceptions import ServiceValidationError

        if self.tank.entry.options.get("control_contract_version", 3) not in (3, 4, 5):
            raise ServiceValidationError("settings_schema_mismatch")
        if self.tank.entry.options.get("control_contract_version") == 5:
            return await self.flow.start(context, guard, request_id, service)
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
            if (
                self.execution_stage.owns_io
                and self.running
                and (not self.execution_stage.task or self.execution_stage.task.done())
            ):
                raise ServiceValidationError("busy")
            if request_id in self.receipts:
                return dict(self.receipts[request_id][1])
            if (
                self.tank.entry.options.get("control_contract_version") == 4
                and sum(bool(x) for x in (self.refill, self.nutrient, self.acid, self.mix)) != 1
            ):
                raise ServiceValidationError("flow_configuration_unsupported")
            if (
                (self.nutrient and self.supports_nutrient)
                or (self.acid and self.supports_acid)
                or (self.mix and self.supports_mix)
            ):
                if self.refill or (self.nutrient and self.acid):
                    raise ServiceValidationError("flow_configuration_unsupported")
                if not self.master or self.fault:
                    raise ServiceValidationError("disabled")
                if self.running:
                    if service:
                        raise ServiceValidationError("busy")
                    return {"accepted": True, "run_id": self.run_id}
                self.run_stage = "mix" if self.mix else "acid" if self.acid else "nutrient"
                await self.execution_stage.start(context, guard)
                self.run_id = uuid.uuid4().hex
                self.stop_context = None
                receipt = {"accepted": True, "run_id": self.run_id}
                if request_id is not None:
                    self.receipts[request_id] = (time.monotonic(), receipt)
                    while len(self.receipts) > 64:
                        self.receipts.pop(next(iter(self.receipts)))
                self.tank.publish()
                return dict(receipt)
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
            self.run_stage = "refill"
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
        if self.flow.active or self.flow.refill.owns_io:
            await self.flow.stop()
        stages = [
            stage
            for stage in (self.nutrient_stage, self.acid_stage, self.mix_stage)
            if stage.owns_io
        ]
        if stages:
            await asyncio.gather(
                *(stage.stop() for stage in stages),
                *([self._stop_refill(state, context=context)] if self._refill_running else []),
            )
            return
        await self._stop_refill(state, context=context)

    async def _stop_refill(self, state, *, context=None):
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
        if self._refill_running:
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
