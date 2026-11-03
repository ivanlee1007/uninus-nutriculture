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


async def test_enable_choices_persist_without_restarting_run(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    assert tank.options["control"].get("automation_enabled") is True
    assert tank.options["control"].get("refill_enabled") is True
    assert await hass.config_entries.async_reload(tank.entry_id)
    await hass.async_block_till_done()
    assert tank.runtime_data.control.master and tank.runtime_data.control.refill
    assert not tank.runtime_data.control.running
    assert not hass.data["p2_fixture"]["calls"]
