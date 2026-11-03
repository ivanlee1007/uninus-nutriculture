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


async def test_on_without_feedback_fails_and_follows_off(control_hass):
    import pytest
    from homeassistant.exceptions import ServiceValidationError
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=1)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    hass.data["p2_fixture"]["hardware"].acknowledge_on = False
    with pytest.raises(ServiceValidationError):
        await toggle(hass, tank, "flow_run")
    assert [c[0] for c in hass.data["p2_fixture"]["calls"]] == ["turn_on", "turn_off"]
    assert tank.runtime_data.control.fault == "start_unconfirmed"


async def test_late_on_after_feedback_timeout_is_followed_by_off(control_hass):
    import asyncio
    import pytest
    from homeassistant.exceptions import ServiceValidationError
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=1)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware.on_entered, hardware.on_release = asyncio.Event(), asyncio.Event()
    with pytest.raises(ServiceValidationError):
        await asyncio.wait_for(toggle(hass, tank, "flow_run"), 3)
    assert tank.runtime_data.control.running, "An unsettled ON cannot be reported stopped"
    hardware.on_release.set()
    await hass.async_block_till_done()
    assert hass.states.get(hardware.entity_id).state == "off"
    assert not tank.runtime_data.control.running
    assert hass.data["p2_fixture"]["calls"][-1][0] == "turn_off"
