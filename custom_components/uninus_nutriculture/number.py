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
        self.generation = 0
        self.live = False
        self.key = key
        self._attr_unique_id = f"{tank.entry.entry_id}:{key}"
        self._attr_name = f"{tank.entry.title} {key.replace('_', ' ')}"
        (
            _,
            self._attr_native_min_value,
            self._attr_native_max_value,
            self._attr_native_step,
            self._attr_native_unit_of_measurement,
        ) = SPECS[key]

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.generation += 1
        self.live = True
        self.tank.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.tank.listeners.discard(self.async_write_ha_state))

    async def async_will_remove_from_hass(self):
        self.live = False
        self.generation += 1
        await super().async_will_remove_from_hass()

    async def async_set_native_value(self, value):
        await self.tank.set_parameter(self.key, value, self, self.generation, self.entity_id)

    @property
    def native_value(self):
        return self.tank.parameters[self.key]
