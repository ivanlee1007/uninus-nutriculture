"""Admission revocation at owned asynchronous boundaries."""

import asyncio

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, configure, toggle  # noqa: F401


async def test_off_revokes_start_waiting_on_controller_lock(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    control = tank.runtime_data.control
    await control.lock.acquire()
    start = asyncio.create_task(toggle(hass, tank, "flow_run"))
    await asyncio.sleep(0.02)
    stop = asyncio.create_task(toggle(hass, tank, "flow_run", False))
    await asyncio.sleep(0.02)
    assert not start.done() and not stop.done()
    control.lock.release()
    result = await asyncio.gather(start, stop, return_exceptions=True)
    assert not hass.data["p2_fixture"]["calls"], "Revoked waiter must never dispatch ON"
    assert isinstance(result[0], ServiceValidationError)


@pytest.mark.parametrize("cause", ["source", "off", "cancel"])
async def test_inflight_on_cannot_escape_safety_cleanup(control_hass, cause):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=1)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware.on_entered, hardware.on_release = asyncio.Event(), asyncio.Event()
    start = asyncio.create_task(toggle(hass, tank, "flow_run"))
    await asyncio.wait_for(hardware.on_entered.wait(), 2)
    stop = None
    if cause == "source":
        hass.states.async_set("sensor.ph", "unavailable")
    elif cause == "off":
        stop = asyncio.create_task(toggle(hass, tank, "flow_run", False))
        await asyncio.sleep(0.02)
    else:
        start.cancel()
        await asyncio.sleep(0.02)
    hardware.on_release.set()
    result = await asyncio.gather(start, return_exceptions=True)
    if stop:
        await stop
    await hass.async_block_till_done()
    assert hass.states.get(hardware.entity_id).state == "off"
    assert hass.data["p2_fixture"]["calls"][-1][0] == "turn_off"
    assert isinstance(result[0], (ServiceValidationError, asyncio.CancelledError))


async def test_removed_native_flow_switch_waiter_cannot_start(control_hass):
    from homeassistant.helpers import entity_registry as er
    from test_p2_control import target

    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    control = tank.runtime_data.control
    await control.lock.acquire()
    start = asyncio.create_task(toggle(hass, tank, "flow_run"))
    await asyncio.sleep(0.02)
    er.async_get(hass).async_remove(target(hass, tank, "switch", "flow_run"))
    await asyncio.sleep(0.02)
    control.lock.release()
    result = await asyncio.gather(start, return_exceptions=True)
    assert not hass.data["p2_fixture"]["calls"]
    assert isinstance(result[0], ServiceValidationError)
