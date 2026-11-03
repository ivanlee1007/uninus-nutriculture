"""Conservative bounds also apply while ON acknowledgement is pending."""
import asyncio
from test_p2_control import add_tank, configure, target, toggle


async def test_timeout_tightening_while_starting_is_not_lost_on_relaxation(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=1)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware.on_entered, hardware.on_release = asyncio.Event(), asyncio.Event()
    start = asyncio.create_task(toggle(hass, tank, "flow_run"))
    await asyncio.wait_for(hardware.on_entered.wait(), 2)
    for value in (1, 190):
        await hass.services.async_call("number", "set_value", {"entity_id": target(hass, tank, "number", "refill_timeout"), "value": value}, blocking=True)
    tank.runtime_data.control.started -= 61
    hardware.on_release.set()
    await asyncio.gather(start, return_exceptions=True)
    await hass.async_block_till_done()
    assert hass.states.get(hardware.entity_id).state == "off"
    assert tank.runtime_data.control.fault == "refill_timeout"
