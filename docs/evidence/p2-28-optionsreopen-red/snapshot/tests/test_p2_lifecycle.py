"""Native lifecycle safety."""
import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from test_p2_control import add_tank, configure, control_hass, toggle  # noqa: F401


@pytest.mark.parametrize("kind", ["unload", "stop"])
async def test_lifecycle_closes_owned_output(control_hass, kind):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    controller = tank.runtime_data.control
    if kind == "unload":
        assert await hass.config_entries.async_unload(tank.entry_id)
    else:
        await hass.async_start()
        await hass.async_stop(force=True)
    assert hass.data["p2_fixture"]["calls"][-1][0] == "turn_off"
    assert controller.running is False
    assert controller.tank.active is False
