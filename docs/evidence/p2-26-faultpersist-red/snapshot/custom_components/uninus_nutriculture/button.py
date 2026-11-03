"""Native emergency and reset controls."""
from homeassistant.components.button import ButtonEntity
from .control_entity import admission_guard


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ControlButton(entry.runtime_data, key) for key in ("emergency_stop", "reset_fault")])


class ControlButton(ButtonEntity):
    def __init__(self, tank, key):
        self.tank = tank
        self.key = key
        self._attr_unique_id = f"{tank.entry.entry_id}:{key}"
        self._attr_name = f"{tank.entry.title} {key}"

    async def async_press(self):
        await self.tank.control.press(self.key, self._context, guard=admission_guard(self))
