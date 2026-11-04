"""Entry-owned nutrient stage, dispatched only through Controller."""

import asyncio
import time

from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError

from .control_auth import authorize
from .control_settings import resolve


class NutrientStage:
    def __init__(self, controller):
        self.control = controller
        self.tank = controller.tank
        self.hass = controller.hass
        self.task = None
        self.clock = time.monotonic
        self.wake = asyncio.Event()
        self.samples = 0
        self.phase = None
        # Last accepted run outcome, independent of the global enable state.
        # None means no settled outcome, including an accepted task not yet entered.
        self.result = None
        self.progress = {"pulse_count": 0, "reserved_on_seconds": 0, "stable_count": 0}
        self.targets = {}
        self.operations = {}
        self.cleaning = False
        self.revoked = None
        self.cleanup_lock = asyncio.Lock()
        self.cleanup_again = False
        self.owns_io = False
        self.pulse_satisfied = False
        self.circulation_confirmed = False
        self.on_since = None
        self.charged_on = 0

    def account_on(self, confirmed_off=False):
        if self.on_since is None:
            return
        charge = max(self.settings["pulse_seconds"], self.clock() - self.on_since)
        self.progress["reserved_on_seconds"] = self.charged_on + charge
        on = self.operations.get(("nutrient", True))
        if confirmed_off and (on is None or on.done()):
            self.charged_on += charge
            self.on_since = None

    @callback
    def changed(self, event):
        import math

        if event.data.get("entity_id") in self.tank.sources.values():
            state = event.data.get("new_state")
            try:
                if state is None or not math.isfinite(float(state.state)):
                    raise ValueError
                key = next(
                    key
                    for key, entity_id in self.tank.sources.items()
                    if entity_id == event.data["entity_id"]
                )
                units = {"ph": (None, "", "pH"), "ec": ("mS/cm",), "level": ("m",)}
                if state.attributes.get("unit_of_measurement") not in units[key]:
                    raise ValueError
                self.revoked = self.revoked or self.unsafe(key, float(state.state))
                if (
                    key == "ec"
                    and self.phase == "pulsing"
                    and float(state.state) >= self.midpoint()
                ):
                    self.pulse_satisfied = True
            except TypeError, ValueError:
                self.revoked = "source_invalid"
        if (
            self.circulation_confirmed
            and not self.cleaning
            and event.data.get("entity_id") == self.targets.get("circulation")
            and ((state := event.data.get("new_state")) is None or state.state != "on")
        ):
            self.revoked = self.revoked or "circulation_lost"
        if event.data.get("entity_id") == self.tank.sources["ec"] and not self.revoked:
            state = event.data.get("new_state")
            token = self.sample_token(state)
            if token is None:
                self.revoked = "sample_invalid"
            if token is not None and (self.last_token is None or token > self.last_token):
                old = event.data.get("old_state")
                mode = self.tank.entry.options["control"].get("sample_mode")
                if (
                    mode != "reported"
                    or old is None
                    or old.state != state.state
                    or event.event_type == "state_reported"
                ):
                    self.samples += 1
                    self.last_token = token
                    self.sample_ec = float(state.state)
        self.wake.set()

    def sample_token(self, state):
        from homeassistant.util import dt as dt_util

        if state is None:
            return None
        config = self.tank.entry.options["control"]
        mode = config.get("sample_mode")
        if mode == "reported":
            return state.last_reported.timestamp()
        value = state.attributes.get(config.get("sample_attribute"))
        if mode == "sequence":
            return value if type(value) is int and value >= 0 else None
        if mode == "timestamp" and isinstance(value, str):
            parsed = dt_util.parse_datetime(value)
            if parsed is not None and parsed.tzinfo is not None:
                age = (dt_util.utcnow() - parsed).total_seconds()
                if 0 <= age <= self.tank.entry.options.get("max_age_seconds", 300):
                    return parsed.timestamp()
        return None

    def phase_changed(self, phase, state):
        self.phase = phase
        self.control.flow_state = state
        self.tank.publish()

    def ec(self):
        return float(self.hass.states.get(self.tank.sources["ec"]).state)

    def midpoint(self):
        value = self.live_midpoint()
        if self.owns_io and hasattr(self, "target_midpoint"):
            self.target_midpoint = min(self.target_midpoint, value)
            return self.target_midpoint
        return value

    def live_midpoint(self):
        from decimal import Decimal

        return float(
            (
                Decimal(str(self.tank.parameters["ec_low"]))
                + Decimal(str(self.tank.parameters["ec_high"]))
            )
            / 2
        )

    def tighten(self):
        if not self.owns_io or not hasattr(self, "settings"):
            return
        live = self.tank.entry.options["dosing_parameters"]
        for key in (
            "pulse_seconds",
            "max_total_on_seconds",
            "max_pulses",
            "flow_timeout_seconds",
            "sample_wait_timeout_seconds",
            "ec_danger_high",
        ):
            self.settings[key] = min(self.settings[key], live[key])
        for key in (
            "safe_min_level_m",
            "ph_danger_low",
            "post_mix_seconds",
            "stable_samples",
            "stable_interval_seconds",
        ):
            self.settings[key] = max(self.settings[key], live[key])
        self.midpoint()
        self.deadline = min(self.deadline, self.started + self.settings["flow_timeout_seconds"])
        self.stage_deadline = min(
            self.stage_deadline, self.started + self.tank.parameters["ec_timeout"] * 60
        )
        self.wake.set()

    def unsafe(self, key, value, *, settings=None):
        if settings is None:
            settings = getattr(self, "settings", self.tank.entry.options["dosing_parameters"])
        if key == "level" and value <= settings["safe_min_level_m"]:
            return "level_unsafe"
        if key == "ec" and value > settings["ec_danger_high"]:
            return "ec_danger"
        if key == "ph" and value < settings["ph_danger_low"]:
            return "ph_danger"
        return None

    def validate(self):
        self.tighten()
        self.account_on()
        if self.control.running and hasattr(self, "deadline") and self.clock() >= self.deadline:
            raise ServiceValidationError("flow_timeout")
        if (
            self.control.running
            and hasattr(self, "stage_deadline")
            and self.clock() >= self.stage_deadline
        ):
            raise ServiceValidationError("ec_timeout")
        if (
            self.owns_io
            and hasattr(self, "settings")
            and self.progress["reserved_on_seconds"] > self.settings["max_total_on_seconds"]
        ):
            raise ServiceValidationError("dose_budget_exhausted")
        self.validate_sources()

    def validate_sources(self):
        if self.revoked:
            raise ServiceValidationError(self.revoked)
        if self.tank.snapshot()[0] == "invalid":
            raise ServiceValidationError("source_invalid")
        if self.sample_token(self.hass.states.get(self.tank.sources["ec"])) is None:
            raise ServiceValidationError("sample_invalid")
        for key, entity_id in self.tank.sources.items():
            reason = self.unsafe(key, float(self.hass.states.get(entity_id).state))
            if reason:
                raise ServiceValidationError(reason)

    async def start(self, context, guard):

        config = self.tank.entry.options.get("control", {})
        # Only a newly requested run may adopt relaxed settings.
        self.settings = dict(self.tank.entry.options["dosing_parameters"])
        self.validate()
        self.targets = {
            role: resolve(self.hass, config.get(role + "_binding"))
            for role in ("nutrient", "circulation")
        }
        for target in self.targets.values():
            state = self.hass.states.get(target)
            if state is None or state.state != "off":
                raise ServiceValidationError("output_not_off")
        await authorize(self.hass, context)
        if guard:
            guard()
        self.generation = self.control.generation
        self.guard = guard
        self.bindings = {role: dict(config[role + "_binding"]) for role in self.targets}
        self.sources = dict(self.tank.sources)
        self.circulation_confirmed = False
        self.revoked = None
        self.operations = {}
        self.owns_io = True
        self.result = None
        self.last_token = self.sample_token(self.hass.states.get(self.tank.sources["ec"]))
        self.on_since = None
        self.charged_on = 0
        self.settings = dict(self.tank.entry.options["dosing_parameters"])
        self.target_midpoint = self.live_midpoint()
        self.started = self.clock()
        self.deadline = self.started + self.settings["flow_timeout_seconds"]
        self.stage_deadline = self.clock() + self.tank.parameters["ec_timeout"] * 60
        self.control.run_context = context
        self.control.flow_state = "starting"
        self.progress = {"pulse_count": 0, "reserved_on_seconds": 0, "stable_count": 0}
        self.task = self.tank.entry.async_create_background_task(
            self.hass, self.run(), "nutrient stage", eager_start=False
        )

    async def wait(self, seconds, predicate=None, bound_key=None):
        began = self.clock()
        end = began + seconds
        while True:
            self.validate()
            if bound_key:
                end = began + self.settings[bound_key]
            if self.clock() >= end:
                break
            for (role, enabled), task in self.operations.items():
                if enabled and task.done():
                    task.result()
            if predicate and predicate():
                return
            self.wake.clear()
            try:
                await asyncio.wait_for(self.wake.wait(), min(0.05, end - self.clock()))
            except TimeoutError:
                pass
        if predicate:
            raise ServiceValidationError("sample_timeout")

    def send(self, role, enabled):
        task = self.operations.get((role, enabled))
        if task is None or task.done():
            task = self.hass.async_create_background_task(
                self.control.nutrient_dispatch(role, enabled),
                "nutrient output",
                eager_start=False,
            )
            if role == "nutrient" and enabled:
                self.on_since = self.clock()
            self.operations[role, enabled] = task
            task.add_done_callback(self.settled)
        return task

    @callback
    def settled(self, task):
        if not task.cancelled():
            task.exception()
        if self.cleaning and any(
            enabled and owned is task for (role, enabled), owned in self.operations.items()
        ):
            self.cleanup_again = True
        if self.owns_io and (not self.task or self.task.done()) and not self.cleaning:
            self.hass.async_create_task(self.cleanup("fault"))

    async def output(self, role, enabled):
        async with asyncio.timeout(self.tank.entry.options["control"].get("feedback_timeout", 10)):
            task = self.send(role, enabled)
            while not task.done():
                if not self.cleaning:
                    self.validate()
                await asyncio.sleep(0.01)
            task.result()
            while (state := self.hass.states.get(self.targets[role])) is None or state.state != (
                "on" if enabled else "off"
            ):
                if not self.cleaning:
                    self.validate()
                await asyncio.sleep(0.01)
            if role == "nutrient" and not enabled:
                self.account_on(confirmed_off=True)
            if enabled:
                await self.control.nutrient_revalidate()

    async def run(self):
        result = "completed"
        try:
            self.phase_changed("starting_circulation", "starting")
            await self.output("circulation", True)
            self.circulation_confirmed = True
            while True:
                self.validate()
                if self.ec() < self.midpoint():
                    if (
                        self.progress["pulse_count"] >= self.settings["max_pulses"]
                        or self.progress["reserved_on_seconds"] + self.settings["pulse_seconds"]
                        > self.settings["max_total_on_seconds"]
                    ):
                        raise ServiceValidationError("dose_budget_exhausted")
                    self.progress["pulse_count"] += 1
                    self.progress["reserved_on_seconds"] += self.settings["pulse_seconds"]
                    self.phase_changed("pulsing", "dosing")
                    self.pulse_satisfied = False
                    on_task = self.send("nutrient", True)
                    try:
                        await self.wait(
                            min(
                                self.settings["pulse_seconds"],
                                max(
                                    0,
                                    self.settings["max_total_on_seconds"] - self.charged_on - 0.05,
                                ),
                            ),
                            lambda: (
                                self.pulse_satisfied
                                or self.ec() >= self.midpoint()
                                or self.clock() - self.on_since >= self.settings["pulse_seconds"]
                            ),
                        )
                    except ServiceValidationError as err:
                        if str(err) != "sample_timeout":
                            raise
                    self.phase_changed("confirming_off", "dosing")
                    await self.output("nutrient", False)
                    if not on_task.done():
                        async with asyncio.timeout(
                            self.tank.entry.options["control"].get("feedback_timeout", 10)
                        ):
                            while not on_task.done():
                                self.validate()
                                await asyncio.sleep(0.01)
                        await self.output("nutrient", False)
                    on_task.result()
                    self.phase_changed("mixing", "mixing")
                    await self.wait(self.settings["post_mix_seconds"], bound_key="post_mix_seconds")
                while True:
                    barrier = self.samples
                    self.phase_changed("waiting_sample", "waiting_sample")
                    await self.wait(
                        self.settings["sample_wait_timeout_seconds"], lambda: self.samples > barrier
                    )
                    self.last_consumed_token = self.last_token
                    if (
                        self.sample_ec >= self.midpoint()
                        and self.sample_ec <= self.tank.parameters["ec_high"]
                    ):
                        self.progress["stable_count"] += 1
                        if self.progress["stable_count"] >= self.settings["stable_samples"]:
                            return
                        self.phase_changed("stabilizing", "stabilizing")
                        await self.wait(
                            self.settings["stable_interval_seconds"],
                            bound_key="stable_interval_seconds",
                        )
                        # Reports inside the minimum interval are not a new evaluation.
                        # Establish a fresh barrier before any further dose or count.
                    else:
                        self.progress["stable_count"] = 0
                        # An above-target sample is not stable, but cannot grant
                        # another pulse from a later stale-token low repaint.
                        if self.sample_ec < self.midpoint():
                            break
        except asyncio.CancelledError:
            result = "aborted"
        except Exception as err:
            self.control.fault = str(err)
            result = "fault"
        finally:
            cleanup = asyncio.create_task(self.cleanup(result))
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    continue
            cleanup.result()

    async def cleanup(self, result):
        async with self.cleanup_lock:
            self.cleaning = True
            self.control.flow_state = "stopping"
            while True:
                self.cleanup_again = False
                nutrient_off = asyncio.create_task(self.output("nutrient", False))
                if not self.control.fault and not self.revoked:
                    # Normal cancellation/completion retains circulation until
                    # dosing OFF confirms. Acute faults still stop both promptly.
                    while not nutrient_off.done():
                        if self.control.fault:
                            break
                        try:
                            self.validate_sources()
                        except ServiceValidationError as err:
                            self.control.fault = str(err)
                            break
                        await asyncio.sleep(0.01)
                outcomes = await asyncio.gather(
                    nutrient_off,
                    self.output("circulation", False),
                    return_exceptions=True,
                )
                if not self.cleanup_again:
                    break
            if self.revoked and not self.control.fault:
                self.control.fault = self.revoked
            failed = any(isinstance(outcome, BaseException) for outcome in outcomes)
            pending = any(not task.done() for task in self.operations.values())
            if failed:
                self.control.fault = "stop_unconfirmed"
            self.owns_io = failed or pending
            self.control.flow_state = (
                "fault" if self.control.fault or self.control.running else result
            )
            # Cleanup is the only outcome authority. Unsettled I/O must not
            # acquire a successful/aborted terminal result.
            if not self.owns_io:
                self.result = self.control.flow_state
            self.cleaning = False
            self.phase = None
            self.tank.publish()

    async def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await asyncio.shield(self.task)
            except asyncio.CancelledError:
                if not self.task.cancelled():
                    raise  # Caller cancelled; the entered run still owns cleanup.
                # Cancellation before run() entered cannot execute its finally.
                cleanup = asyncio.create_task(self.cleanup("aborted"))
                while not cleanup.done():
                    try:
                        await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        continue
                cleanup.result()
                if asyncio.current_task().cancelling():
                    raise
        elif self.owns_io:
            await self.cleanup("aborted")
