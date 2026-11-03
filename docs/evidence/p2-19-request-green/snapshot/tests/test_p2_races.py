"""Admission revocation at owned asynchronous boundaries."""
import asyncio
import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, configure, control_hass, toggle  # noqa: F401


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
