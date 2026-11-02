from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def put(p, s):
    p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding='utf-8')
put('custom_components/uninus_nutriculture/const.py', '''"""Public parameters and fixed shadow contract."""
DOMAIN = "uninus_nutriculture"
# default, native minimum, maximum, step, unit
SPECS = {
    "level_low": (2.25, 0, 10, 0.01, "m"),
    "level_high": (2.4, 0, 10, 0.01, "m"),
    "ph_low": (5.4, 0, 14, 0.1, None),
    "ph_high": (5.8, 0, 14, 0.1, None),
    "ec_low": (0.8, 0, 20, 0.01, "mS/cm"),
    "ec_high": (0.9, 0, 20, 0.01, "mS/cm"),
    "refill_timeout": (190, 1, 1440, 1, "min"),
    "ec_timeout": (90, 1, 1440, 1, "min"),
    "ph_timeout": (190, 1, 1440, 1, "min"),
    "mix_duration": (10, 1, 1440, 1, "min"),
}
SOURCE_KEYS = ("ph", "ec", "level")
''')
put('custom_components/uninus_nutriculture/__init__.py', '''"""UNiNUS Nutriculture: read-only shadow observation, never actuation."""
from homeassistant.const import Platform
from .manager import Tank

async def async_setup_entry(hass, entry):
    entry.runtime_data = Tank(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.NUMBER])
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True

async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.NUMBER, Platform.SENSOR])
''')
put('custom_components/uninus_nutriculture/manager.py', '''"""Per-entry shared state; contains no output/service dispatch."""
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN, SOURCE_KEYS, SPECS

class Tank:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.parameters = {key: spec[0] for key, spec in SPECS.items()}

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
''')
put('custom_components/uninus_nutriculture/number.py', '''"""Native administrator-editable configuration numbers."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import EntityCategory
from .const import SPECS

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(TankNumber(entry.runtime_data, key) for key in SPECS)

class TankNumber(NumberEntity):
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, tank, key):
        self.tank = tank
        self.key = key
        self._attr_unique_id = f"{tank.entry.entry_id}:{key}"
        self._attr_name = f"{tank.entry.title} {key.replace('_', ' ')}"
        _, self._attr_native_min_value, self._attr_native_max_value, self._attr_native_step, self._attr_native_unit_of_measurement = SPECS[key]

    @property
    def native_value(self):
        return self.tank.parameters[self.key]
''')
put('custom_components/uninus_nutriculture/sensor.py', '''"""Frozen shadow-status contract for consumers."""
from homeassistant.components.sensor import SensorEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TankStatus(entry.runtime_data)])

class TankStatus(SensorEntity):
    _attr_should_poll = False

    def __init__(self, tank):
        self.tank = tank
        self._attr_unique_id = f"{tank.entry.entry_id}:status"
        self._attr_name = f"{tank.entry.title} status"

    @property
    def native_value(self):
        return self.tank.snapshot()[0]

    @property
    def extra_state_attributes(self):
        return self.tank.snapshot()[1]
''')
