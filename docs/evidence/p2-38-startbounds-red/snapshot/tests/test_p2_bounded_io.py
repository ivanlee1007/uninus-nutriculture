"""The integration bounds its waiter even when a provider ignores cancellation."""
import asyncio
from test_p2_control import add_tank, configure, toggle


async def test_cancellation_resistant_off_provider_does_not_extend_deadline(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=1)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware.off_release = asyncio.Event()
    loop = asyncio.get_running_loop()
    release = loop.call_later(2.2, hardware.off_release.set)
    started = loop.time()
    try:
        await toggle(hass, tank, "flow_run", False)
        elapsed = loop.time() - started
        assert elapsed < 1.8, f"OFF waiter exceeded its deadline: {elapsed}"
        assert tank.runtime_data.control.running
        assert tank.runtime_data.control.fault == "stop_unconfirmed"
    finally:
        release.cancel()
        hardware.off_release.set()
        await hass.async_block_till_done()
