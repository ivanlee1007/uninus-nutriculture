"""Native entry-owned control switches."""

from homeassistant.components.switch import SwitchEntity

from .control_entity import admission_guard

KEYS = (
    "automation_enabled",
    "refill_enabled",
    "nutrient_enabled",
    "acid_enabled",
    "mix_enabled",
    "flow_run",
)


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

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.tank.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.tank.listeners.discard(self.async_write_ha_state))

    @property
    def available(self):
        return self.tank.active and (
            self.key in ("automation_enabled", "refill_enabled", "flow_run")
            or (self.key == "nutrient_enabled" and self.tank.control.supports_nutrient)
        )

    @property
    def is_on(self):
        control = self.tank.control
        return {
            "automation_enabled": control.master,
            "refill_enabled": control.refill,
            "nutrient_enabled": control.nutrient,
            "flow_run": control.running,
        }.get(self.key, False)

    async def async_turn_on(self, **kwargs):
        await self.tank.control.action(self.key, True, self._context, guard=admission_guard(self))

    async def async_turn_off(self, **kwargs):
        await self.tank.control.action(self.key, False, self._context, guard=admission_guard(self))
