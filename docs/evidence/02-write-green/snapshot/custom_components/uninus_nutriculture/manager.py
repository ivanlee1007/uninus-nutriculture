"""Per-entry shared state; contains no output/service dispatch."""
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN, SOURCE_KEYS, SPECS

class Tank:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.parameters = {key: spec[0] for key, spec in SPECS.items()}
        self.listeners = set()

    def publish(self):
        for listener in tuple(self.listeners):
            listener()

    async def set_parameter(self, key, value):
        candidate = {**self.parameters, key: value}
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
        return {
            key: row.entity_id
            for key in SPECS
            if (entity_id := registry.async_get_entity_id("number", DOMAIN, f"{self.entry.entry_id}:{key}"))
            and (row := registry.async_get(entity_id))
            and row.config_entry_id == self.entry.entry_id
            and not row.disabled_by
            and self.hass.states.get(entity_id) is not None
        }

    def snapshot(self):
        reasons = []
        for key, entity_id in self.sources.items():
            value = float(self.hass.states.get(entity_id).state)
            if not self.parameters[key + "_low"] <= value <= self.parameters[key + "_high"]:
                reasons.append(key + "_out_of_range")
        return ("out_of_range" if reasons else "within_range"), {
            "schema_version": 1, "mode": "shadow", "ready_for_irrigation": False,
            "source_entities": self.sources, "parameter_entities": self.targets(),
            "parameters": dict(self.parameters), "reasons": reasons,
        }
