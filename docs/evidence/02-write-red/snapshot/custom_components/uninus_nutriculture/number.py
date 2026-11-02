"""Native administrator-editable configuration numbers."""
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
