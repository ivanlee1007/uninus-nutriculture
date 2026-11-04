"""P3b native Options and actuator tracer bullets (fake hardware only)."""

import asyncio

import pytest
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from test_p2_control import add_tank, target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native

Q = dict(
    safe_min_level_m=0.5,
    pulse_seconds=2,
    max_total_on_seconds=20,
    max_pulses=5,
    post_mix_seconds=1,
    sample_wait_timeout_seconds=5,
    stable_samples=1,
    stable_interval_seconds=1,
    flow_timeout_seconds=20,
)


def acid_values(hass):
    pump, circ = hass.data["p3_fixture"]["rows"]
    return dict(
        ph="sensor.ph",
        ec="sensor.ec",
        level="sensor.level",
        max_age_seconds=300,
        feedback_timeout=1,
        acid_output=pump.entity_id,
        circulation_output=circ.entity_id,
        acid_commissioned=True,
        acid_device_max_on_seconds=3,
        acid_protection_confirmed=True,
        acid_alias_notes="Independent fixture acid pump",
        acid_sample_mode="sequence",
        acid_sample_attribute="sample",
        acid_report_contract_confirmed=False,
        circulation_device_max_on_seconds=30,
        circulation_protection_confirmed=True,
        circulation_alias_notes="Independent fixture circulation cutoff",
        **{"acid_" + k: v for k, v in Q.items()},
    )


async def save_acid(hass, entry):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    try:
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"], acid_values(hass)
        )
    except InvalidData:
        result = None
    assert entry.options.get("acid_parameters") == Q, "Real Options must persist acid-only Q"
    assert result["type"] == FlowResultType.CREATE_ENTRY
    return result


async def test_acid_options_save_reopen_native_enable_zero_io(dosing_hass):
    hass = dosing_hass
    entry = await add_tank(hass)
    await save_acid(hass, entry)
    assert entry.options["control_contract_version"] == 4
    assert not entry.options["control"].get("nutrient_binding")
    assert not entry.options["control"].get("binding")
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {str(k): k.description or {} for k in flow["data_schema"].schema}
    assert fields["acid_pulse_seconds"]["suggested_value"] == 2
    assert fields["acid_commissioned"]["suggested_value"] is True
    hass.config_entries.options.async_abort(flow["flow_id"])
    assert hass.states.get(target(hass, entry, "switch", "acid_enabled")).state == "off"
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "acid_enabled")
    assert hass.states.get(target(hass, entry, "switch", "acid_enabled")).state == "on"
    assert not hass.data["p3_fixture"]["calls"]
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize("entrance", ["service", "switch"])
async def test_acid_native_midpoint_mix_fresh_ph_complete(dosing_hass, entrance):
    hass = dosing_hass
    entry = await add_tank(hass)
    await save_acid(hass, entry)
    hass.states.async_set("sensor.ph", "6.5", {"sample": 2})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "acid_enabled")
    pump, circ = hass.data["p3_fixture"]["outputs"]
    try:
        if entrance == "service":
            await start_native(hass, entry)
        else:
            await toggle(hass, entry, "flow_run")
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        assert circ.is_on
        hass.states.async_set("sensor.ph", "5.6", {"sample": 3})
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        assert not pump.is_on and circ.is_on
        async with asyncio.timeout(3):
            while entry.runtime_data.control.flow_state != "waiting_sample":
                await asyncio.sleep(0.01)
        hass.states.async_set("sensor.ec", ".85", {"unit_of_measurement": "mS/cm", "sample": 99})
        await asyncio.sleep(0.1)
        assert entry.runtime_data.control.running
        hass.states.async_set("sensor.ph", "5.6", {"sample": 4})
        async with asyncio.timeout(2):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert entry.runtime_data.control.flow_state == "completed"
        assert not circ.is_on
    finally:
        await toggle(hass, entry, "flow_run", False)
