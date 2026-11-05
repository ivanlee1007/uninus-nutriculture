"""Readonly permission, deliberately without a safety/danger device class."""

from homeassistant.components.binary_sensor import BinarySensorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([IrrigationPermit(entry.runtime_data)])


class IrrigationPermit(BinarySensorEntity):
    _attr_should_poll = False

    def __init__(self, tank):
        self.tank = tank
        self._attr_unique_id = f"{tank.entry.entry_id}:irrigation_permit"
        self._attr_name = f"{tank.entry.title} 允許灌溉"

    async def async_added_to_hass(self):
        self.tank.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.tank.listeners.discard(self.async_write_ha_state))

    @property
    def is_on(self):
        try:
            return self.tank.quality.dto()["permit"]["granted"]
        except Exception:
            return False

    @property
    def extra_state_attributes(self):
        try:
            d = self.tank.quality.dto()
        except Exception:
            return {}
        return {
            **{
                k: d[k]
                for k in ("schema_version", "config_entry_id", "epoch", "observation_revision")
            },
            **{k: d["permit"][k] for k in ("run_id", "expires_at", "reasons")},
        }
