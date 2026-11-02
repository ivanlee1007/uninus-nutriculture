"""Frozen shadow-status contract for consumers."""
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
