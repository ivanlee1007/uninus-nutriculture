"""Frozen shadow-status contract for consumers."""

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TankStatus(entry.runtime_data)])


class TankStatus(SensorEntity):
    _attr_should_poll = False

    def __init__(self, tank):
        self.tank = tank
        self._attr_unique_id = f"{tank.entry.entry_id}:status"
        self._attr_name = f"{tank.entry.title} status"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.tank.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.tank.listeners.discard(self.async_write_ha_state))
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, list(self.tank.sources.values()), self._source_changed
            )
        )
        self.async_on_remove(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._number_changed)
        )
        self.async_on_remove(self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._number_changed))
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._source_changed, timedelta(seconds=5), cancel_on_shutdown=True
            )
        )

    @callback
    def _number_changed(self, event):
        if event.data.get("entity_id", "").startswith("number."):
            self.async_write_ha_state()

    @callback
    def _source_changed(self, event):
        self.async_write_ha_state()

    @property
    def native_value(self):
        return self.tank.snapshot()[0]

    @property
    def extra_state_attributes(self):
        return self.tank.snapshot()[1]
