"""Standalone policy on the shared owned-I/O stage machinery."""

import asyncio
import math

from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .control_auth import authorize
from .control_settings import resolve
from .nutrient import NutrientStage


class MixStage(NutrientStage):
    def __init__(self, controller):
        super().__init__(controller, "mix")

    def validate_sources(self, *, reset=False):
        if self.revoked and not reset:
            raise ServiceValidationError(self.revoked)
        if self.control.flow.active and not reset:
            self.control.flow.validate_sources("mix")
        state = self.hass.states.get(self.tank.sources["level"])
        try:
            value = float(state.state)
            age = (dt_util.utcnow() - state.last_reported).total_seconds()
            if (
                not math.isfinite(value)
                or state.attributes.get("unit_of_measurement") != "m"
                or not 0 <= age <= self.tank.entry.options.get("max_age_seconds", 300)
            ):
                raise ValueError
        except AttributeError, TypeError, ValueError:
            raise ServiceValidationError("source_invalid") from None
        settings = (
            self.control.flow.settings("mix")
            if self.control.flow.active
            else self.tank.entry.options["mix_parameters"]
        )
        if value < settings["safe_min_level_m"]:
            raise ServiceValidationError("level_unsafe")

    def validate(self):
        self.validate_sources()
        if self.control.flow.active and hasattr(self, "circ_physical_cutoff"):
            import time

            if time.monotonic() >= self.circ_physical_cutoff:
                raise ServiceValidationError("flow_timeout")
        if self.clock() >= self.deadline:
            raise ServiceValidationError("flow_timeout")

    def tighten(self):
        if self.owns_io:
            self.deadline = min(
                self.deadline,
                self.started + self.tank.entry.options["mix_parameters"]["flow_timeout_seconds"],
            )
            self.end = min(self.end, self.started + self.tank.parameters["mix_duration"] * 60)
            self.wake.set()

    @callback
    def changed(self, event):
        if event.data.get("entity_id") == self.tank.sources["level"]:
            state = event.data.get("new_state")
            try:
                if (
                    state is None
                    or not math.isfinite(float(state.state))
                    or state.attributes.get("unit_of_measurement") != "m"
                ):
                    raise ValueError
                if (
                    float(state.state)
                    < (
                        self.control.flow.settings("mix")
                        if self.control.flow.active
                        else self.tank.entry.options["mix_parameters"]
                    )["safe_min_level_m"]
                ):
                    self.revoked = "level_unsafe"
            except ValueError, TypeError:
                self.revoked = "source_invalid"
        if (
            self.circulation_confirmed
            and not self.cleaning
            and event.data.get("entity_id") == self.targets.get("circulation")
        ):
            state = event.data.get("new_state")
            if state is None or state.state != "on":
                self.revoked = "circulation_lost"
        self.wake.set()

    async def start(self, context, guard):
        config = self.tank.entry.options["control"]
        settings = (
            self.control.flow.settings("mix")
            if self.control.flow.active
            else self.tank.entry.options["mix_parameters"]
        )
        params = self.control.flow.params if self.control.flow.active else self.tank.parameters
        self.started = self.clock()
        self.deadline = self.started + min(
            settings["flow_timeout_seconds"],
            config["circulation_device_max_on_seconds"] - config.get("feedback_timeout", 10),
        )
        self.end = self.started + params["mix_duration"] * 60
        self.validate()
        self.bindings = {"circulation": dict(config["circulation_binding"])}
        self.targets = {"circulation": resolve(self.hass, self.bindings["circulation"])}
        state = self.hass.states.get(self.targets["circulation"])
        shared = self.control.flow.active and self.control.leases and state and state.state == "on"
        if not shared and (state is None or state.state != "off"):
            raise ServiceValidationError("output_not_off")
        await authorize(self.hass, context)
        if guard:
            guard()
        self.guard = guard
        self.generation = self.control.generation
        self.sources = dict(self.tank.sources)
        self.operations = {}
        self.owns_io = True
        self.result = None
        self.revoked = None
        self.circulation_confirmed = False
        self.control.run_context = context
        self.control.flow_state = "starting"
        self.task = self.tank.entry.async_create_background_task(
            self.hass, self.run(), "standalone mix", eager_start=False
        )

    async def run(self):
        result = "completed"
        try:
            self.phase_changed("starting_circulation", "starting")
            await self.output("circulation", True)
            self.circulation_confirmed = True
            self.phase_changed("mixing", "mixing")
            while self.clock() < self.end:
                self.validate()
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), 0.05)
                except TimeoutError:
                    pass
        except asyncio.CancelledError:
            result = "aborted"
        except Exception as err:
            self.control.fault = self.control.fault or str(err)
            result = "fault"
        finally:
            cleanup = asyncio.create_task(self.cleanup(result))
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    continue
            cleanup.result()
