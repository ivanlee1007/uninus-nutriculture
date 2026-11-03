"""Accepted runs retain conservative parameter bounds."""
import pytest
from test_p2_control import add_tank, configure, control_hass, target, toggle  # noqa: F401


@pytest.mark.parametrize("change", ["relax_high", "tighten_timeout"])
async def test_native_number_does_not_expand_run_bounds(control_hass, change):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    if change == "relax_high":
        key, value = "level_high", 2.5
    else:
        key, value = "refill_timeout", 1
        tank.runtime_data.control.started -= 61
    await hass.services.async_call("number", "set_value", {"entity_id": target(hass, tank, "number", key), "value": value}, blocking=True)
    if change == "relax_high":
        hass.states.async_set("sensor.level", 2.4, {"unit_of_measurement": "m"})
    await hass.async_block_till_done()
    assert hass.data["p2_fixture"]["calls"][-1][0] == "turn_off"
