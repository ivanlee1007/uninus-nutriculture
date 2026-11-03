"""Stop acknowledgement is truth, not optimism."""
from test_p2_control import add_tank, configure, control_hass, target, toggle  # noqa: F401


async def test_stop_without_feedback_keeps_flow_on_and_fault(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=1)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    hass.data["p2_fixture"]["hardware"].acknowledge_off = False
    await toggle(hass, tank, "flow_run", False)
    assert hass.states.get(target(hass, tank, "switch", "flow_run")).state == "on"
    assert tank.runtime_data.control.fault == "stop_unconfirmed"
    assert tank.runtime_data.control.flow_state == "fault"
    hass.data["p2_fixture"]["hardware"].acknowledge_off = True
    await toggle(hass, tank, "flow_run", False)
