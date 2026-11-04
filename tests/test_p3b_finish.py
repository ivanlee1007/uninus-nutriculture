"""Bounded finish regressions through actual Core entries and dispatcher."""

import asyncio

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3b_safety import acid_ready
from test_p3b_wire import payload


@pytest.mark.parametrize("group", ["acid_parameters", "safety_parameters", "parameters"])
async def test_writer_explicit_null_is_not_omission(dosing_hass, group):
    hass = dosing_hass
    entry = await acid_ready(hass)
    tank = entry.runtime_data
    before = dict(entry.options)
    async with tank.lock:
        with pytest.raises(ServiceValidationError):
            tank.write_settings(**{group: None}, expected_revision=before["settings_revision"])
    assert dict(entry.options) == before
    async with tank.lock:
        tank.write_settings(expected_revision=before["settings_revision"])
    assert dict(entry.options) == before


async def test_null_uncommissioned_preserves_draft_and_safety_mirror(dosing_hass):
    hass = dosing_hass
    entry = await acid_ready(hass)
    await toggle(hass, entry, "automation_enabled", False)
    data = payload(hass, entry)
    data["safety_parameters"] = {**data["safety_parameters"], "ph_high_alarm": 6.9}
    await hass.services.async_call(
        "uninus_nutriculture", "apply_control_settings_v4", data, blocking=True
    )
    assert entry.options["dosing_parameters"]["ph_high_alarm"] == 6.9
    assert entry.options["acid_parameters"] == data["acid_parameters"]
    assert not hass.data["p3_fixture"]["calls"]


@pytest.mark.parametrize("cause", ["transient", "held_off", "identity"])
async def test_acid_held_owner_acute_cleanup(dosing_hass, cause):
    from homeassistant.helpers import entity_registry as er

    hass = dosing_hass
    entry = await acid_ready(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    pump.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    try:
        if cause == "identity":
            row = hass.data["p3_fixture"]["rows"][0]
            er.async_get(hass).async_update_entity(
                row.entity_id, new_unique_id="foreign-replacement"
            )
        elif cause == "held_off":
            pump.off_ack_gate = asyncio.Event()
            stop = asyncio.create_task(toggle(hass, entry, "flow_run", False))
            await asyncio.wait_for(pump.entered_off.wait(), 1)
            hass.states.async_set("sensor.ph", "3.7", {"sample": 3})
        else:
            hass.states.async_set("sensor.ph", "unavailable")
            hass.states.async_set("sensor.ph", "6.5", {"sample": 3})
        await asyncio.wait_for(circ.entered_off.wait(), 0.8)
        assert not circ.is_on
        assert entry.runtime_data.control.running
        if cause == "identity":
            assert not pump.entered_off.is_set(), "Never dispatch OFF to replacement identity"
        else:
            assert not pump.is_on
    finally:
        pump.on_ack_gate.set()
        if pump.off_ack_gate:
            pump.off_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)
        if cause == "held_off":
            await stop


async def test_idle_acid_emergency_does_not_serialize_circulation_off(dosing_hass):
    hass = dosing_hass
    entry = await acid_ready(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    for output in (pump, circ):
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
        await asyncio.wait_for(circ.entered_off.wait(), 0.7)
        assert entry.runtime_data.control.running
    finally:
        pump.off_ack_gate.set()
        await task
