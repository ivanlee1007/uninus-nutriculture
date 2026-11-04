"""Native B1 output and captured event safety regressions."""

import asyncio

import pytest
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native


@pytest.mark.parametrize(
    "source,bad,good,unit,reason",
    [
        ("ec", "0.7", "0.7", "wrong", "source_invalid"),
        ("level", "0.1", "1.0", "m", "level_unsafe"),
        ("ec", "1.4", "0.7", "mS/cm", "ec_danger"),
        ("ph", "3.7", "6.0", "pH", "ph_danger"),
    ],
)
async def test_circulation_pending_latches_event(dosing_hass, source, bad, good, unit, reason):
    hass = dosing_hass
    entry = await prepared(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    circ.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(circ.entered_on.wait(), 2)
        hass.states.async_set("sensor." + source, bad, {"unit_of_measurement": unit})
        valid_unit = {"ec": "mS/cm", "level": "m", "ph": "pH"}[source]
        hass.states.async_set("sensor." + source, good, {"unit_of_measurement": valid_unit})
        await asyncio.wait_for(circ.entered_off.wait(), 0.75)
        assert entry.runtime_data.control.fault == reason
        assert not pump.entered_on.is_set()
    finally:
        circ.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)


async def test_midpoint_transient_is_not_erased(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        hass.states.async_set("sensor.ec", "0.85", {"unit_of_measurement": "mS/cm"})
        hass.states.async_set("sensor.ec", "0.7", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        assert not pump.is_on
        assert ("nutrient", "device_local_cutoff") not in hass.data["p3_fixture"]["calls"]
    finally:
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize("lost", ["off", "unknown"])
async def test_circulation_loss_latches_even_when_recovered(dosing_hass, lost):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        hass.states.async_set(circ.entity_id, lost)
        hass.states.async_set(circ.entity_id, "on")
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        assert entry.runtime_data.control.fault == "circulation_lost"
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_failed_nutrient_off_still_closes_circulation(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, feedback_timeout=1)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    pump.fail_off = True
    try:
        await toggle(hass, entry, "flow_run", False)
        assert circ.entered_off.is_set(), (
            "Nutrient OFF failure must not skip independent circulation closure"
        )
        assert not circ.is_on
        assert entry.runtime_data.control.running
        assert entry.runtime_data.control.fault == "stop_unconfirmed"
    finally:
        pump.fail_off = False
        await entry.runtime_data.control.stop()


@pytest.mark.parametrize("role_index", [0, 1])
async def test_late_physical_on_is_quarantined_and_closed(dosing_hass, role_index):
    from homeassistant.exceptions import HomeAssistantError

    hass = dosing_hass
    entry = await prepared(hass, feedback_timeout=1)
    output = hass.data["p3_fixture"]["outputs"][role_index]
    output.on_apply_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(output.entered_on.wait(), 2)
        await toggle(hass, entry, "flow_run", False)
        assert entry.runtime_data.control.running
        with pytest.raises(HomeAssistantError, match="busy"):
            await start_native(hass, entry)
        # A finished stage with unsettled I/O must still use nutrient cleanup.
        await toggle(hass, entry, "flow_run", False)
        output.entered_off.clear()
        output.on_apply_gate.set()
        await asyncio.wait_for(output.entered_off.wait(), 1)
        async with asyncio.timeout(2):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert not output.is_on
        assert ("nutrient", "device_local_cutoff") not in hass.data["p3_fixture"]["calls"]
    finally:
        output.on_apply_gate.set()
        await entry.runtime_data.control.stop()


async def test_late_on_during_other_role_off_ack_cannot_report_stopped(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, feedback_timeout=1)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    pump.on_apply_gate = asyncio.Event()
    circ.off_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    stop = None
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        stop = asyncio.create_task(toggle(hass, entry, "flow_run", False))
        await asyncio.wait_for(circ.entered_off.wait(), 1)
        pump.entered_off.clear()
        pump.on_apply_gate.set()
        await asyncio.sleep(0.05)
        circ.off_ack_gate.set()
        await asyncio.wait_for(stop, 2)
        async with asyncio.timeout(1):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert not pump.is_on, (
            "Late ON during cleanup must trigger another OFF before stopped truth"
        )
        assert pump.entered_off.is_set()
    finally:
        pump.on_apply_gate.set()
        circ.off_ack_gate.set()
        if stop:
            await asyncio.gather(stop, return_exceptions=True)
        await entry.runtime_data.control.stop()


async def test_removed_identity_never_sends_off_to_reused_foreign_name(dosing_hass):
    from homeassistant.helpers import entity_registry as er

    hass = dosing_hass
    entry = await prepared(hass, feedback_timeout=1)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    old_id = pump.entity_id
    er.async_get(hass).async_remove(old_id)
    await asyncio.sleep(0.05)
    foreign = type(pump)("foreign")
    foreign.entity_id = old_id
    await hass.data["switch"].async_add_entities([foreign])
    await asyncio.wait_for(circ.entered_off.wait(), 0.75)
    await entry.runtime_data.control.stop()
    assert not foreign.entered_off.is_set(), "Reused entity_id does not transfer ownership"
    assert circ.entered_off.is_set(), "Other independently proven role must still close"
    assert entry.runtime_data.control.running
    assert entry.runtime_data.control.fault == "stop_unconfirmed"


async def test_pending_circulation_invalid_recovered_revokes_immediately(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    circ.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(circ.entered_on.wait(), 2)
        hass.states.async_set("sensor.ec", "unavailable", {"unit_of_measurement": "mS/cm"})
        hass.states.async_set("sensor.ec", "0.7", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(circ.entered_off.wait(), 0.75)
        assert entry.runtime_data.control.fault == "source_invalid"
        assert not pump.entered_on.is_set()
    finally:
        circ.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)
