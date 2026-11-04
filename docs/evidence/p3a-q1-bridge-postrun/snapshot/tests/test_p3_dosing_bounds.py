"""Native B2 bounds; physical I/O remains Controller-owned."""

import asyncio
import time

import pytest
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native
from test_p3_settings import apply, payload


async def until(predicate, seconds=4):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_actual_send_to_confirmed_off_blocks_next_full_reservation(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, max_total_on_seconds=2)
    stage = entry.runtime_data.control.nutrient_stage
    pump, _ = hass.data["p3_fixture"]["outputs"]
    pump.off_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_off.wait(), 2)
        await asyncio.sleep(0.35)
        pump.off_ack_gate.set()
        await until(lambda: stage.phase == "waiting_sample")
        hass.states.async_set("sensor.ec", "0.71", {"unit_of_measurement": "mS/cm"})
        await asyncio.sleep(0.2)
        assert hass.data["p3_fixture"]["calls"].count(("nutrient", "on")) == 1
        assert entry.runtime_data.control.fault == "dose_budget_exhausted"
    finally:
        pump.off_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize("role", ["nutrient", "circulation"])
async def test_ec_minutes_deadline_interrupts_held_native_on_ack(dosing_hass, role):
    hass = dosing_hass
    entry = await prepared(hass, flow_timeout_seconds=120)
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": target(hass, entry, "number", "ec_timeout"),
            "value": 1,
        },
        blocking=True,
    )
    stage = entry.runtime_data.control.nutrient_stage
    output = hass.data["p3_fixture"]["outputs"][0 if role == "nutrient" else 1]
    output.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(output.entered_on.wait(), 2)
        # Advance only this owned domain clock, never SDK/global time.
        stage.clock = lambda: time.monotonic() + 61
        stage.wake.set()
        await asyncio.wait_for(output.entered_off.wait(), 0.75)
        assert not output.on_ack_gate.is_set()
        assert entry.runtime_data.control.running
        assert entry.runtime_data.control.fault == "ec_timeout"
    finally:
        output.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize("change", ["safe_min", "pulse", "midpoint_relax", "midpoint_tighten"])
async def test_hot_bounds_are_monotone_through_native_writer(dosing_hass, change):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    stage = entry.runtime_data.control.nutrient_stage
    pump, _ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        data = payload(entry)
        if change == "safe_min":
            data["dosing_parameters"]["safe_min_level_m"] = float(
                hass.states.get("sensor.level").state
            )
        elif change == "pulse":
            await asyncio.sleep(1.1)
            data["dosing_parameters"]["pulse_seconds"] = 1
        elif change == "midpoint_relax":
            data["parameters"].update(ec_low=0.9, ec_high=1.1)
        else:
            data["parameters"].update(ec_low=0.5, ec_high=0.8)
        runtime = entry.runtime_data
        await apply(hass, data)
        assert entry.runtime_data is runtime
        if change == "midpoint_relax":
            hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(pump.entered_off.wait(), 0.4)
        assert not pump.is_on
        if change == "safe_min":
            assert entry.runtime_data.control.fault == "level_unsafe"
        else:
            assert stage.progress["pulse_count"] == 1
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_unknown_on_interval_over_budget_aborts_while_ack_is_held(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, max_total_on_seconds=1)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    pump.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_off.wait(), 2)
        await asyncio.sleep(0.2)
        assert entry.runtime_data.control.fault == "dose_budget_exhausted"
        assert not pump.on_ack_gate.is_set()
        assert entry.runtime_data.control.running
        await asyncio.wait_for(circ.entered_off.wait(), 0.5)
    finally:
        pump.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)


async def test_hot_mix_extension_is_committed_and_cannot_be_shortened(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    stage = entry.runtime_data.control.nutrient_stage
    await start_native(hass, entry)
    try:
        await until(lambda: stage.phase == "mixing")
        began = time.monotonic()
        data = payload(entry)
        data["dosing_parameters"]["post_mix_seconds"] = 2
        await apply(hass, data)
        data = payload(entry)
        data["dosing_parameters"]["post_mix_seconds"] = 1
        await apply(hass, data)
        await asyncio.sleep(1.15)
        assert stage.phase == "mixing"
        await until(lambda: stage.phase == "waiting_sample", 2)
        assert time.monotonic() - began >= 1.9
    finally:
        await toggle(hass, entry, "flow_run", False)
