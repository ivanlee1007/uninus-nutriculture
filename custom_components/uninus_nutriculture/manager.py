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


_UNSET = object()


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
            self.write_settings(
                parameters={**self.entry.options.get("parameters", self.parameters), key: value},
                expected_revision=self.entry.options.get("settings_revision", 0),
            )

    def write_settings(
        self,
        *,
        parameters=_UNSET,
        dosing_parameters=_UNSET,
        acid_parameters=_UNSET,
        mix_parameters=_UNSET,
        safety_parameters=_UNSET,
        control=_UNSET,
        sources=_UNSET,
        expected_revision=None,
        _recipe_catalog=_UNSET,
    ):
        """Synchronous commit under Tank.lock. No await between admission and effect."""
        from .control_settings import DAYS, STAGES
        from .dosing_settings import validate_dosing

        if not self.active:
            raise ServiceValidationError("entry_not_loaded")
        options = dict(self.entry.options)
        if options.get("control_contract_version", 3) not in (3, 4, 5):
            raise ServiceValidationError("settings_schema_mismatch")
        revision = options.get("settings_revision", 0)
        if expected_revision is not None and (
            type(expected_revision) is not int
            or expected_revision < 0
            or expected_revision != revision
        ):
            raise ServiceValidationError("settings_conflict")
        # Null is a protocol value, never an alias for omitted arguments.
        for name, value in (
            ("parameters", parameters),
            ("control", control),
            ("sources", sources),
            ("safety_parameters", safety_parameters),
        ):
            if value is None:
                raise ServiceValidationError("invalid_parameters")
        config_input = control if control is not _UNSET else options.get("control", {})
        for name, value, role in (
            ("dosing", dosing_parameters, "nutrient"),
            ("acid", acid_parameters, "acid"),
            ("mix", mix_parameters, "mix"),
        ):
            if value is None and config_input.get(role + "_commissioned"):
                raise ServiceValidationError("invalid_commissioning")
        candidate = dict(options)
        params = dict(
            parameters if parameters is not _UNSET else options.get("parameters", self.parameters)
        )
        validate(params)
        config = dict(control if control is not _UNSET else options.get("control", {}))
        days = config.get("allowed_weekdays", {key: list(DAYS) for key in STAGES})
        if set(days) != set(STAGES) or any(
            not isinstance(value, list)
            or any(day not in DAYS for day in value)
            or len(value) != len(set(value))
            for value in days.values()
        ):
            raise ServiceValidationError("invalid_weekdays")
        if options.get("control_contract_version") == 5 and days != options["control"].get(
            "allowed_weekdays"
        ):
            raise ServiceValidationError("settings_schema_mismatch")
        dosing = (
            dosing_parameters
            if dosing_parameters is not _UNSET and dosing_parameters is not None
            else options.get("dosing_parameters")
        )
        if dosing is not None:
            if config.get("nutrient_commissioned") or (
                acid_parameters is _UNSET
                and mix_parameters is _UNSET
                and options.get("control_contract_version") not in (4, 5)
            ):
                validate_dosing(params, dosing, config)
            candidate["dosing_parameters"] = dict(dosing)
        elif config.get("nutrient_commissioned"):
            raise ServiceValidationError("invalid_dosing_parameters")
        if (
            acid_parameters is not _UNSET
            or mix_parameters is not _UNSET
            or options.get("control_contract_version") in (4, 5)
        ):
            from .p3b_settings import validate_v4

            validate_v4(
                params,
                candidate,
                config,
                None if acid_parameters is _UNSET else acid_parameters,
                None if mix_parameters is _UNSET else mix_parameters,
                None if safety_parameters is _UNSET else safety_parameters,
            )
        if options.get("control_contract_version") == 5:
            candidate["control_contract_version"] = 5
        if parameters is not _UNSET or "parameters" in options:
            candidate["parameters"] = params
        if control is not _UNSET:
            candidate["control"] = config
        if sources is not _UNSET:
            candidate.update(sources)
        if candidate != options:
            candidate["settings_revision"] = revision + 1
        if _recipe_catalog is not _UNSET:
            candidate["recipe_catalog"] = _recipe_catalog
        if candidate != options:
            self.hass.config_entries.async_update_entry(self.entry, options=candidate)
            self.parameters = params
            self.publish()
        return self.entry.options.get("settings_revision", 0)

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
