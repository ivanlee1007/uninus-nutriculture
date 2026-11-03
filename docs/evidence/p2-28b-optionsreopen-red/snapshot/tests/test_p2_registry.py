"""Stable registry identity and invalidation."""
import pytest
from homeassistant.helpers import entity_registry as er
from test_p2_control import add_tank, configure, control_hass, toggle  # noqa: F401


async def test_running_registry_identity_change_faults(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    er.async_get(hass).async_update_entity(hass.data["p2_fixture"]["row"].entity_id, new_unique_id="replacement")
    await hass.async_block_till_done()
    assert tank.runtime_data.control.fault is not None
    assert tank.runtime_data.control.flow_state == "fault"


async def test_other_tank_cannot_commission_shared_output(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    other = await add_tank(hass)
    result = await configure(hass, other)
    assert result["errors"]["base"] == "output_already_owned"
    assert not other.options.get("control", {}).get("commissioned")
    assert not hass.data["p2_fixture"]["calls"]
