"""Native entry-owned control switches."""
from homeassistant.components.switch import SwitchEntity

KEYS = ("automation_enabled", "refill_enabled", "nutrient_enabled", "acid_enabled", "mix_enabled", "flow_run")


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ControlSwitch(entry.runtime_data, key) for key in KEYS])


class ControlSwitch(SwitchEntity):
    _attr_should_poll = False

    def __init__(self, tank, key):
        self.tank = tank
        self.key = key
        self._attr_unique_id = f"{tank.entry.entry_id}:{key}"
        self._attr_name = f"{tank.entry.title} {key}"
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs):
        pass

    async def async_turn_off(self, **kwargs):
        pass
