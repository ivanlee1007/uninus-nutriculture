"""Finite P3a finish gates at actual native control entrypoints."""

import asyncio
from datetime import timedelta

import pytest
from homeassistant.auth import auth_manager_from_config
from homeassistant.core import Context
from homeassistant.util import dt as dt_util
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native
from test_p3_dosing_bounds import until


async def test_native_immediate_flow_off_releases_accepted_ownership(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    control = entry.runtime_data.control
    try:
        await start_native(hass, entry)
        await toggle(hass, entry, "flow_run", False)
        assert not control.running
        assert not control.nutrient_stage.owns_io
        assert all(not output.is_on for output in hass.data["p3_fixture"]["outputs"])
    finally:
        await control.stop()


async def test_stage_disable_retains_aborted_owner_not_idle_or_refill_history(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, _ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    await toggle(hass, entry, "nutrient_enabled", False)
    await hass.async_block_till_done()
    status = hass.states.get(target(hass, entry, "sensor", "control_status"))
    assert status.state == "aborted"
    assert status.attributes["stage_states"]["nutrient"] == "aborted"
    assert status.attributes["stage_states"]["refill"] == "skipped_disabled"
    assert not entry.runtime_data.control.running
    assert all(not output.is_on for output in hass.data["p3_fixture"]["outputs"])


async def test_deleted_run_user_cannot_block_midpoint_off_or_causal_trace(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("owner")
    admin = await hass.auth.async_create_user("admin", group_ids=["system-admin"])
    origin = Context(user_id=admin.id)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    pump.on_ack_gate = asyncio.Event()
    await hass.services.async_call(
        "uninus_nutriculture",
        "start_flow",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
        context=origin,
    )
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        await hass.auth.async_remove_user(admin)
        hass.states.async_set("sensor.ec", "0.85", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        assert not pump.on_ack_gate.is_set()
        off = [
            row for row in hass.data["p3_fixture"]["contexts"] if row[:2] == ("nutrient", "off")
        ][-1][2]
        assert off.user_id is None and off.parent_id == origin.id
        pump.on_ack_gate.set()
        await until(lambda: not entry.runtime_data.control.running)
        assert not circ.is_on and entry.runtime_data.control.fault is not None
        assert hass.data["p3_fixture"]["calls"].count(("nutrient", "on")) == 1
    finally:
        pump.on_ack_gate.set()
        await entry.runtime_data.control.stop()


@pytest.mark.parametrize("mode", ["sequence", "timestamp"])
async def test_invalid_token_event_revokes_even_when_current_frame_recovers(dosing_hass, mode):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2, sample_mode=mode, sample_attribute="sample")
    # Native Core treats attribute True == 1 as unchanged; use 2 so the
    # invalid bool frame is actually emitted, without patching the SDK.
    token = 2 if mode == "sequence" else dt_util.utcnow().isoformat()
    invalid = True if mode == "sequence" else (dt_util.utcnow() + timedelta(days=1)).isoformat()
    attrs = {"unit_of_measurement": "mS/cm", "sample": token}
    hass.states.async_set("sensor.ec", "0.70", attrs)
    pump, _ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        hass.states.async_set("sensor.ec", "0.70", {**attrs, "sample": invalid})
        hass.states.async_set("sensor.ec", "0.70", attrs)
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        await until(lambda: not entry.runtime_data.control.running)
        assert entry.runtime_data.control.fault == "sample_invalid"
    finally:
        await entry.runtime_data.control.stop()


async def test_normal_stop_keeps_circulation_until_nutrient_off_is_confirmed(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    pump.off_ack_gate = asyncio.Event()
    stopper = asyncio.create_task(toggle(hass, entry, "flow_run", False))
    try:
        await asyncio.wait_for(pump.entered_off.wait(), 1)
        await asyncio.sleep(0.05)
        assert circ.is_on, (
            "Normal stop must retain circulation while dosing OFF is still unconfirmed"
        )
        assert entry.runtime_data.control.running
    finally:
        pump.off_ack_gate.set()
        await asyncio.wait_for(stopper, 2)
    assert not circ.is_on and not entry.runtime_data.control.running


@pytest.mark.parametrize("source", ["state", "settings"])
async def test_unsafe_during_normal_stop_stops_circulation_and_latches(dosing_hass, source):
    from test_p3_settings import apply, payload

    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    pump.off_ack_gate = asyncio.Event()
    stopper = asyncio.create_task(toggle(hass, entry, "flow_run", False))
    try:
        await asyncio.wait_for(pump.entered_off.wait(), 1)
        if source == "state":
            hass.states.async_set("sensor.level", "0.4", {"unit_of_measurement": "m"})
            hass.states.async_set("sensor.level", "2.0", {"unit_of_measurement": "m"})
        else:
            data = payload(entry)
            data["dosing_parameters"]["safe_min_level_m"] = 2.0
            await apply(hass, data)
        await asyncio.wait_for(circ.entered_off.wait(), 0.75)
        assert not pump.off_ack_gate.is_set()
    finally:
        pump.off_ack_gate.set()
        await asyncio.wait_for(stopper, 2)
    assert entry.runtime_data.control.fault == "level_unsafe"
    assert not entry.runtime_data.control.master


async def test_control_sensor_updates_on_actual_output_events_not_periodic_tick(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        await hass.async_block_till_done()
        status = hass.states.get(target(hass, entry, "sensor", "control_status"))
        assert pump.is_on and circ.is_on
        assert status.attributes["output_states"] == {"nutrient": "on", "circulation": "on"}
    finally:
        await entry.runtime_data.control.stop()
