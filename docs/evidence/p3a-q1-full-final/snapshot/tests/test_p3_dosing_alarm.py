"""High-pH timed reason is observational, never an implicit emergency."""

import asyncio
import time

from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native


async def test_high_ph_delay_reason_is_native_visible_and_does_not_abort(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, ph_high_alarm_seconds=1)
    control = entry.runtime_data.control
    status = target(hass, entry, "sensor", "control_status")
    hass.states.async_set("sensor.ph", "7.0", {"unit_of_measurement": "pH"})
    hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
    await hass.async_block_till_done()
    assert "ph_high_alarm" not in hass.states.get(status).attributes["reasons"]
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(hass.data["p3_fixture"]["outputs"][1].entered_on.wait(), 1)
        # Only the owned stage/observer clock advances; SDK and wall time remain real.
        control.nutrient_stage.clock = lambda: time.monotonic() + 1.1
        control.tick(None)
        await hass.async_block_till_done()
        assert "ph_high_alarm" in hass.states.get(status).attributes["reasons"]
        assert control.running and control.fault is None
        assert hass.data["p3_fixture"]["outputs"][1].is_on
        hass.states.async_set("sensor.ph", "6.8", {"unit_of_measurement": "pH"})
        await hass.async_block_till_done()
        assert "ph_high_alarm" not in hass.states.get(status).attributes["reasons"]
    finally:
        await toggle(hass, entry, "flow_run", False)
