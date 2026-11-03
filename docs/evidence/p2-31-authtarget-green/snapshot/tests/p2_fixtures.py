"""Isolated native SwitchEntity hardware; never replaces service routing."""

import pytest_asyncio
from conftest import make_hass
from homeassistant.helpers import entity_registry as er


@pytest_asyncio.fixture
async def control_hass(tmp_path):
    hass = await make_hass(tmp_path / "control-ha")
    for key, value, unit in (("ph", 5.6, "pH"), ("ec", 0.85, "mS/cm"), ("level", 2, "m")):
        hass.states.async_set("sensor." + key, value, {"unit_of_measurement": unit})
    calls = []

    from homeassistant.components.switch import SwitchEntity
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "switch", {})

    class Hardware(SwitchEntity):
        _attr_name = "Fixture refill"
        _attr_unique_id = "refill-output"
        _attr_is_on = False
        _attr_should_poll = False
        acknowledge_off = True
        acknowledge_on = True
        on_entered = None
        on_release = None

        async def async_turn_on(self, **kwargs):
            calls.append(("turn_on", {"entity_id": self.entity_id}, self._context))
            if self.on_entered:
                self.on_entered.set()
                await self.on_release.wait()
            if self.acknowledge_on:
                self._attr_is_on = True
                self.async_write_ha_state()

        async def async_turn_off(self, **kwargs):
            calls.append(("turn_off", {"entity_id": self.entity_id}, self._context))
            if self.acknowledge_off:
                self._attr_is_on = False
                self.async_write_ha_state()

    hardware = Hardware()
    await hass.data["switch"].async_add_entities([hardware])
    row = er.async_get(hass).async_get(hardware.entity_id)
    hass.data["p2_fixture"] = {"row": row, "calls": calls, "hardware": hardware}
    yield hass
    await hass.async_stop(force=True)
