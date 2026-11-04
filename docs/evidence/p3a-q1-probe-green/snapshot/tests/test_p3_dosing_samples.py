"""Stable sample consumption uses real native report events."""

import asyncio

import pytest
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native
from test_p3_dosing_bounds import until


async def test_stable_interval_cached_low_cannot_start_a_new_dose(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, stable_samples=2)
    stage = entry.runtime_data.control.nutrient_stage
    hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
    await start_native(hass, entry)
    try:
        await until(lambda: stage.phase == "waiting_sample")
        hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
        await until(lambda: stage.phase == "stabilizing")
        hass.states.async_set("sensor.ec", "0.70", {"unit_of_measurement": "mS/cm"})
        await asyncio.sleep(1.2)
        assert ("nutrient", "on") not in hass.data["p3_fixture"]["calls"], (
            "Interval expiry cannot dose using cached EC"
        )
        hass.states.async_set("sensor.ec", "0.70", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(hass.data["p3_fixture"]["outputs"][0].entered_on.wait(), 1)
        assert stage.progress["stable_count"] == 0
    finally:
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize("accepted_ec", ["0.86", "1.0"])
async def test_old_token_burst_cannot_replace_the_consumed_sample_value(dosing_hass, accepted_ec):
    hass = dosing_hass
    entry = await prepared(
        hass, stable_samples=2, sample_mode="sequence", sample_attribute="sample"
    )
    stage = entry.runtime_data.control.nutrient_stage
    attrs = {"unit_of_measurement": "mS/cm", "sample": 1}
    hass.states.async_set("sensor.ec", "0.86", attrs)
    await start_native(hass, entry)
    try:
        await until(lambda: stage.phase == "waiting_sample")
        hass.states.async_set("sensor.ec", accepted_ec, {**attrs, "sample": 2})
        hass.states.async_set("sensor.ec", "0.70", attrs)
        await asyncio.sleep(0.2)
        assert ("nutrient", "on") not in hass.data["p3_fixture"]["calls"]
        assert stage.progress["stable_count"] == (1 if accepted_ec == "0.86" else 0)
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_invalid_report_revokes_without_escaping_native_event_callback(dosing_hass, caplog):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, _ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        hass.states.async_set("sensor.ec", "unavailable", {"unit_of_measurement": "mS/cm"})
        hass.states.async_set("sensor.ec", "0.70", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        await until(lambda: entry.runtime_data.control.fault == "source_invalid")
        assert not [
            record
            for record in caplog.records
            if record.name == "homeassistant.core" and record.exc_info
        ], "Invalid telemetry must be contained by the native listener"
    finally:
        await toggle(hass, entry, "flow_run", False)
