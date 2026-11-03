"""Emergency stop and explicit reset."""

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, configure, target, toggle  # noqa: F401


async def press(hass, tank, key):
    await hass.services.async_call(
        "button", "press", {"entity_id": target(hass, tank, "button", key)}, blocking=True
    )


async def test_emergency_latches_until_reset_without_reenable(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    await press(hass, tank, "emergency_stop")
    assert hass.data["p2_fixture"]["calls"][-1][0] == "turn_off"
    assert tank.runtime_data.control.fault == "emergency_stop"
    with pytest.raises(ServiceValidationError):
        await toggle(hass, tank, "flow_run")
    await press(hass, tank, "reset_fault")
    assert tank.runtime_data.control.fault is None
    assert tank.runtime_data.control.master is False
    assert [c[0] for c in hass.data["p2_fixture"]["calls"]] == ["turn_on", "turn_off"]


async def test_emergency_latch_survives_reload_and_reset_persists_disabled(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await press(hass, tank, "emergency_stop")
    assert await hass.config_entries.async_reload(tank.entry_id)
    assert tank.runtime_data.control.fault == "emergency_stop"
    assert tank.runtime_data.control.master is False
    await press(hass, tank, "reset_fault")
    assert await hass.config_entries.async_reload(tank.entry_id)
    assert tank.runtime_data.control.fault is None
    assert tank.runtime_data.control.master is False
