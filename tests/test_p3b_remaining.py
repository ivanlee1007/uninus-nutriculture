"""Compact new-role acceptance; native Options, dispatcher and lifecycle."""

import asyncio

import pytest
from homeassistant.data_entry_flow import FlowResultType
from test_p2_control import add_tank, target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3b_safety import acid_ready


async def mix_ready(hass):
    entry = await add_tank(hass)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": target(hass, entry, "number", "mix_duration"), "value": 1},
        blocking=True,
    )
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        dict(
            ph="sensor.ph",
            ec="sensor.ec",
            level="sensor.level",
            max_age_seconds=300,
            circulation_output=hass.data["p3_fixture"]["rows"][1].entity_id,
            feedback_timeout=1,
            mix_commissioned=True,
            mix_safe_min_level_m=0.5,
            mix_flow_timeout_seconds=120,
            circulation_device_max_on_seconds=90,
            circulation_protection_confirmed=True,
            circulation_alias_notes="Fixture only",
        ),
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    hass.states.async_set("sensor.ph", "unavailable")
    hass.states.async_set("sensor.ec", "unavailable")
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    return entry


async def test_mixed_commission_emergency_starts_every_off_before_held_acid_ack(dosing_hass):
    hass = dosing_hass
    entry = await acid_ready(
        hass, commissioned=True, refill_output=hass.data["p2_fixture"]["row"].entity_id
    )
    pump, circ = hass.data["p3_fixture"]["outputs"]
    refill = hass.data["p2_fixture"]["hardware"]
    for output in (pump, circ, refill):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": output.entity_id}, blocking=True
        )
    pump.off_ack_gate = asyncio.Event()
    task = asyncio.create_task(
        hass.services.async_call(
            "button",
            "press",
            {"entity_id": target(hass, entry, "button", "emergency_stop")},
            blocking=True,
        )
    )
    try:
        await asyncio.wait_for(pump.entered_off.wait(), 1)
        async with asyncio.timeout(0.7):
            while refill.is_on:
                await asyncio.sleep(0.01)
        assert circ.entered_off.is_set()
        assert not task.done(), "Held ACK still owns emergency cleanup"
    finally:
        pump.off_ack_gate.set()
        await task


@pytest.mark.parametrize("fault_source", [False, True])
async def test_mix_level_only_reset_zero_io(dosing_hass, fault_source):
    hass = dosing_hass
    entry = await mix_ready(hass)
    if fault_source:
        await start_native(hass, entry)
        await asyncio.wait_for(hass.data["p3_fixture"]["outputs"][1].entered_on.wait(), 2)
        hass.states.async_set("sensor.level", ".1", {"unit_of_measurement": "m"})
        async with asyncio.timeout(2):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        hass.states.async_set("sensor.level", "2", {"unit_of_measurement": "m"})
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": target(hass, entry, "button", "emergency_stop")},
        blocking=True,
    )
    count = len(hass.data["p3_fixture"]["calls"])
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": target(hass, entry, "button", "reset_fault")},
        blocking=True,
    )
    assert entry.runtime_data.control.fault is None
    assert not entry.runtime_data.control.master
    assert len(hass.data["p3_fixture"]["calls"]) == count


@pytest.mark.parametrize("ending", ["stop", "unload"])
async def test_mix_actual_core_lifecycle(dosing_hass, ending):
    hass = dosing_hass
    entry = await mix_ready(hass)
    _, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    await asyncio.wait_for(circ.entered_on.wait(), 2)
    if ending == "stop":
        await hass.async_stop(force=True)
    else:
        assert await hass.config_entries.async_unload(entry.entry_id)
    assert circ.entered_off.is_set() and not circ.is_on


@pytest.mark.parametrize("cause", ["revoked", "off_failure", "late_apply", "ph_repaint", "cutoff"])
async def test_acid_remaining_owned_boundaries(dosing_hass, cause):
    from homeassistant.auth import auth_manager_from_config
    from homeassistant.core import Context

    hass = dosing_hass
    entry = await acid_ready(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    context = Context()
    if cause == "revoked":
        hass.auth = await auth_manager_from_config(hass, [], [])
        await hass.auth.async_create_user("owner")
        admin = await hass.auth.async_create_user("admin", group_ids=["system-admin"])
        context = Context(user_id=admin.id)
        circ.on_ack_gate = asyncio.Event()
    if cause == "late_apply":
        pump.on_apply_gate = asyncio.Event()
    await hass.services.async_call(
        "uninus_nutriculture",
        "start_flow",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        context=context,
    )
    try:
        if cause == "revoked":
            await asyncio.wait_for(circ.entered_on.wait(), 2)
            await hass.auth.async_update_user(admin, is_active=False)
            circ.on_ack_gate.set()
            await asyncio.wait_for(circ.entered_off.wait(), 2)
            assert not pump.entered_on.is_set()
        else:
            await asyncio.wait_for(pump.entered_on.wait(), 2)
            if cause == "off_failure":
                pump.fail_off = True
                hass.states.async_set("sensor.ph", "3.7", {"sample": 3})
            elif cause == "late_apply":
                hass.states.async_set("sensor.ph", "unavailable")
                await asyncio.wait_for(circ.entered_off.wait(), 1)
                pump.on_apply_gate.set()
            elif cause == "ph_repaint":
                hass.states.async_set("sensor.ph", "5.6", {"sample": 3})
                await asyncio.wait_for(pump.entered_off.wait(), 1)
                async with asyncio.timeout(3):
                    while entry.runtime_data.control.flow_state != "waiting_sample":
                        await asyncio.sleep(0.01)
                hass.states.async_set("sensor.ph", "5.6", {"sample": 3, "repaint": True})
                await asyncio.sleep(0.1)
                assert entry.runtime_data.control.running
                assert entry.runtime_data.control.acid_stage.progress["stable_count"] == 0
                return
            else:
                stage = entry.runtime_data.control.acid_stage
                now = stage.clock()
                stage.clock = lambda: now + 31  # domain clock seam; real Options remain valid
                stage.wake.set()
            await asyncio.wait_for(circ.entered_off.wait(), 2)
            assert not circ.is_on
        if cause != "ph_repaint":
            assert entry.runtime_data.control.fault
    finally:
        pump.fail_off = False
        if pump.on_apply_gate:
            pump.on_apply_gate.set()
        if circ.on_ack_gate:
            circ.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)
