"""Native emergency/reset and Core lifecycle, never a live-device fixture."""

import asyncio

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import target
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native


async def test_idle_emergency_closes_both_commissioned_external_on_outputs(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    for output in (pump, circ):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": output.entity_id}, blocking=True
        )
    assert not entry.runtime_data.control.running
    try:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": target(hass, entry, "button", "emergency_stop")},
            blocking=True,
        )
        await asyncio.wait_for(
            asyncio.gather(pump.entered_off.wait(), circ.entered_off.wait()), 0.75
        )
        assert not pump.is_on and not circ.is_on
        assert entry.runtime_data.control.fault == "emergency_stop"
        assert not entry.runtime_data.control.running
    finally:
        for output in (pump, circ):
            await hass.services.async_call(
                "switch", "turn_off", {"entity_id": output.entity_id}, blocking=True
            )


@pytest.mark.parametrize("source,value", [("level", "0.5"), ("ph", "3.7"), ("ec", "1.4")])
async def test_reset_rejects_valid_but_dangerous_nutrient_sources(dosing_hass, source, value):
    hass = dosing_hass
    entry = await prepared(hass)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": target(hass, entry, "button", "emergency_stop")},
        blocking=True,
    )
    entity_id = "sensor." + source
    hass.states.async_set(entity_id, value, dict(hass.states.get(entity_id).attributes))
    with pytest.raises(ServiceValidationError, match="reset_unsafe"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": target(hass, entry, "button", "reset_fault")},
            blocking=True,
        )
    assert entry.runtime_data.control.fault == "emergency_stop"
    assert not entry.runtime_data.control.master


@pytest.mark.parametrize("kind", ["unload", "stop"])
async def test_actual_core_lifecycle_closes_nutrient_and_circulation(dosing_hass, kind):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    control = entry.runtime_data.control
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    if kind == "unload":
        assert await hass.config_entries.async_unload(entry.entry_id)
    else:
        await hass.async_start()
        await hass.async_stop(force=True)
    assert not pump.is_on and not circ.is_on
    assert not control.running and not control.tank.active
    assert not [
        call for call in hass.data["p3_fixture"]["calls"] if call[1] == "device_local_cutoff"
    ]


async def test_nutrient_only_options_updates_keep_native_idle_projection(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    await hass.async_block_till_done()
    status = hass.states.get(target(hass, entry, "sensor", "control_status"))
    assert status.state == "idle"
    assert status.attributes["flow_state"] == "idle"
    assert not hass.data["p3_fixture"]["calls"]


async def test_mixed_commissioning_idle_emergency_closes_all_three_roles(dosing_hass):
    hass = dosing_hass
    refill = hass.data["p2_fixture"]["hardware"]
    entry = await prepared(hass, commissioned=True, refill_output=refill.entity_id)
    outputs = [refill, *hass.data["p3_fixture"]["outputs"]]
    for output in outputs:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": output.entity_id}, blocking=True
        )
    try:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": target(hass, entry, "button", "emergency_stop")},
            blocking=True,
        )
        assert all(not output.is_on for output in outputs), (
            "Emergency must close every commissioned role, not just the selected stage"
        )
        assert not entry.runtime_data.control.running
        assert entry.runtime_data.control.fault == "emergency_stop"
    finally:
        for output in outputs:
            await hass.services.async_call(
                "switch", "turn_off", {"entity_id": output.entity_id}, blocking=True
            )


@pytest.mark.parametrize("held_role", ["refill", "nutrient"])
async def test_mixed_emergency_retains_running_until_each_native_off_ack(dosing_hass, held_role):
    hass = dosing_hass
    refill = hass.data["p2_fixture"]["hardware"]
    entry = await prepared(
        hass, commissioned=True, refill_output=refill.entity_id, feedback_timeout=1
    )
    pump, circ = hass.data["p3_fixture"]["outputs"]
    gate = asyncio.Event()
    if held_role == "refill":
        refill.off_release = gate
    else:
        pump.off_ack_gate = gate
    for output in (refill, pump, circ):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": output.entity_id}, blocking=True
        )
    try:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": target(hass, entry, "button", "emergency_stop")},
            blocking=True,
        )
        assert entry.runtime_data.control.running, (
            "One owner's completed cleanup cannot hide another owner's pending OFF"
        )
        assert not circ.is_on
        if held_role == "refill":
            assert not pump.is_on
        else:
            assert not refill.is_on
        gate.set()
        async with asyncio.timeout(2):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert all(not output.is_on for output in (refill, pump, circ))
        assert entry.runtime_data.control.fault is not None
    finally:
        gate.set()
        await entry.runtime_data.control.stop()
