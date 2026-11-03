"""Per-entry shared state; contains no output/service dispatch."""

import asyncio
import math
from decimal import Decimal

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SOURCE_KEYS, SPECS


def validate(parameters):
    """Validate the entire candidate before any mutation."""
    if set(parameters) != set(SPECS):
        raise ServiceValidationError("invalid_parameters")
    for key, value in parameters.items():
        _, minimum, maximum, step, _ = SPECS[key]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not minimum <= value <= maximum
            or (Decimal(str(value)) - Decimal(str(minimum))) % Decimal(str(step)) != 0
        ):
            raise ServiceValidationError("invalid_parameter_value")
    for key in SOURCE_KEYS:
        if parameters[key + "_low"] >= parameters[key + "_high"]:
            raise ServiceValidationError("invalid_parameter_pair")


class Tank:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.parameters = dict(
            entry.options.get("parameters", {key: spec[0] for key, spec in SPECS.items()})
        )
        validate(self.parameters)
        self.binding = dict(self.sources)
        self.active = True
        self.lock = asyncio.Lock()
        self.listeners = set()

    def publish(self):
        for listener in tuple(self.listeners):
            listener()

    async def set_parameter(self, key, value, entity, generation, entity_id):
        async with self.lock:
            registry = er.async_get(self.hass)
            row = registry.async_get(entity_id)
            if (
                not self.active
                or not entity.live
                or entity.generation != generation
                or entity.entity_id != entity_id
                or row is None
                or row.disabled_by
                or row.platform != DOMAIN
                or row.config_entry_id != self.entry.entry_id
                or row.unique_id != f"{self.entry.entry_id}:{key}"
                or self.hass.data["number"].get_entity(entity_id) is not entity
            ):
                raise ServiceValidationError("inactive_parameter_entity")
            candidate = {**self.parameters, key: value}
            validate(candidate)
            # Native ConfigEntry storage schedules a save; not crash-durable fsync.
            self.hass.config_entries.async_update_entry(
                self.entry, options={**self.entry.options, "parameters": candidate}
            )
            self.parameters = candidate
            self.publish()

    @property
    def sources(self):
        return {key: self.entry.options.get(key, self.entry.data[key]) for key in SOURCE_KEYS}

    def targets(self):
        registry = er.async_get(self.hass)
        targets = {}
        for key in SPECS:
            entity_id = registry.async_get_entity_id(
                "number", DOMAIN, f"{self.entry.entry_id}:{key}"
            )
            if (
                entity_id is None
                or (row := registry.async_get(entity_id)) is None
                or row.config_entry_id != self.entry.entry_id
                or row.disabled_by
                or (state := self.hass.states.get(entity_id)) is None
            ):
                continue
            try:
                if not math.isfinite(float(state.state)):
                    continue
            except TypeError, ValueError:
                continue
            targets[key] = row.entity_id
        return targets

    def snapshot(self):
        reasons = []
        invalid = False
        units = {"ph": (None, "", "pH"), "ec": ("mS/cm",), "level": ("m",)}
        for key, entity_id in self.sources.items():
            state = self.hass.states.get(entity_id)
            reason = None
            if state is None:
                reason = key + "_missing"
            elif state.attributes.get("unit_of_measurement") not in units[key]:
                reason = key + "_unit"
            else:
                try:
                    value = float(state.state)
                    if not math.isfinite(value):
                        raise ValueError
                except TypeError, ValueError:
                    reason = key + "_invalid"
            if not reason:
                max_age = self.entry.options.get(
                    "max_age_seconds", self.entry.data.get("max_age_seconds", 300)
                )
                age = (dt_util.utcnow() - state.last_reported).total_seconds()
                if age < 0 or age > max_age:
                    reason = key + "_stale"
            if reason:
                reasons.append(reason)
                invalid = True
            elif not self.parameters[key + "_low"] <= value <= self.parameters[key + "_high"]:
                reasons.append(key + "_out_of_range")
        return ("invalid" if invalid else "out_of_range" if reasons else "within_range"), {
            "schema_version": 1,
            "mode": "shadow",
            "ready_for_irrigation": False,
            "source_entities": self.sources,
            "parameter_entities": self.targets(),
            "parameters": dict(self.parameters),
            "reasons": reasons,
        }
