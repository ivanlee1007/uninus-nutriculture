"""A new ON during stopping is rejected, never queued for later."""

import asyncio

from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, configure, toggle


async def test_fast_off_on_does_not_queue_restart(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=1)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware.acknowledge_off = False
    stop = asyncio.create_task(toggle(hass, tank, "flow_run", False))
    for _ in range(100):
        if tank.runtime_data.control.flow_state == "stopping":
            break
        await asyncio.sleep(0.002)
    assert tank.runtime_data.control.flow_state == "stopping"
    start = asyncio.create_task(toggle(hass, tank, "flow_run"))
    await asyncio.sleep(0.02)
    hardware.acknowledge_off = True
    hardware._attr_is_on = False
    hardware.async_write_ha_state()
    result = await asyncio.gather(start, stop, return_exceptions=True)
    assert [c[0] for c in hass.data["p2_fixture"]["calls"]] == ["turn_on", "turn_off"]
    assert isinstance(result[0], ServiceValidationError)
