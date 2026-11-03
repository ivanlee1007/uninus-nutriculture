"""Reload is never an automatic run."""
from test_p2_control import add_tank, configure, control_hass, toggle  # noqa: F401


async def test_reload_with_bound_output_on_faults_without_commands(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    assert await hass.config_entries.async_unload(tank.entry_id)
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware._attr_is_on = True
    hardware.async_write_ha_state()
    assert await hass.config_entries.async_setup(tank.entry_id)
    await hass.async_block_till_done()
    assert tank.runtime_data.control.flow_state == "fault"
    assert tank.runtime_data.control.fault == "restart_output_not_off"
    assert not hass.data["p2_fixture"]["calls"]
