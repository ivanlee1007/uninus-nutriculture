"""Native safety, migration, and schema4 authority acceptance."""

import asyncio

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native
from test_p3b_native import acid_values


async def acid_ready(hass, **updates):
    entry = await add_tank(hass)
    values = {**acid_values(hass), **updates}
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert result["type"] == FlowResultType.CREATE_ENTRY, result
    hass.states.async_set("sensor.ph", "6.5", {"sample": 2})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "acid_enabled")
    return entry


@pytest.mark.parametrize(
    "cause", ["emergency", "normal", "invalid", "bool", "level", "ph", "ec", "late", "reset"]
)
async def test_acid_native_owned_stop_and_fault(dosing_hass, cause):
    hass = dosing_hass
    entry = await acid_ready(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    if cause == "late":
        pump.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    try:
        if cause in ("emergency", "reset"):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": target(hass, entry, "button", "emergency_stop")},
                blocking=True,
            )
        elif cause == "normal":
            await toggle(hass, entry, "flow_run", False)
        elif cause == "late":
            hass.states.async_set("sensor.ph", "unavailable")
        elif cause == "invalid":
            hass.states.async_set("sensor.ph", "unavailable")
        elif cause == "bool":
            hass.states.async_set("sensor.ph", "6.5", {"sample": True})
        elif cause == "level":
            hass.states.async_set("sensor.level", ".1", {"unit_of_measurement": "m"})
        elif cause == "ph":
            hass.states.async_set("sensor.ph", "3.7", {"sample": 3})
        else:
            hass.states.async_set("sensor.ec", "1.4", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        await asyncio.wait_for(circ.entered_off.wait(), 0.75)
        assert not pump.is_on and not circ.is_on
        if cause == "late":
            assert entry.runtime_data.control.running
            pump.on_ack_gate.set()
        async with asyncio.timeout(2):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        if cause == "normal":
            assert entry.runtime_data.control.flow_state == "aborted"
        else:
            assert entry.runtime_data.control.fault is not None
        if cause == "reset":
            hass.states.async_set("sensor.ph", "5.6", {"sample": 3})
            count = len(hass.data["p3_fixture"]["calls"])
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": target(hass, entry, "button", "reset_fault")},
                blocking=True,
            )
            assert entry.runtime_data.control.fault is None
            assert len(hass.data["p3_fixture"]["calls"]) == count
    finally:
        if pump.on_ack_gate:
            pump.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)


async def test_n_only_options_injected_defaults_do_not_upgrade(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    await toggle(hass, entry, "automation_enabled", False)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    values = {}
    for key in flow["data_schema"].schema:
        suggestion = (key.description or {}).get("suggested_value")
        if suggestion is not None:
            values[str(key)] = suggestion
    values.update(ph="sensor.ph", ec="sensor.ec", level="sensor.level", max_age_seconds=300)
    values.update(
        acid_commissioned=False,
        acid_protection_confirmed=False,
        acid_report_contract_confirmed=False,
        mix_commissioned=False,
        circulation_protection_confirmed=False,
    )
    result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert result["type"] == FlowResultType.CREATE_ENTRY, result
    assert entry.options.get("control_contract_version", 3) == 3
    assert entry.options["control"]["nutrient_commissioned"]


async def test_v4_snapshot_and_old_writer_rejected(dosing_hass):
    hass = dosing_hass
    entry = await acid_ready(hass)
    status = hass.states.get(target(hass, entry, "sensor", "control_status")).attributes
    assert status["schema_version"] == 4
    assert status["acid_parameters"]["pulse_seconds"] == 2
    assert status["dosing_parameters"] is None
    assert status["mix_parameters"] is None
    assert set(status["safety_parameters"]) == {
        "ph_danger_low",
        "ec_danger_high",
        "ph_high_alarm",
        "ph_high_alarm_seconds",
    }
    assert status["settings_target"]["service"] == "apply_control_settings_v4"
    assert status["capabilities"]["acid"] is True
    assert status["capabilities"]["mix"] is False
    with pytest.raises(ServiceValidationError, match="settings_schema_mismatch"):
        await hass.services.async_call(
            "uninus_nutriculture",
            "apply_control_settings",
            {
                "config_entry_id": entry.entry_id,
                "expected_revision": entry.options["settings_revision"],
                "parameters": dict(entry.runtime_data.parameters),
                "dosing_parameters": {},
                "allowed_weekdays": dict(entry.options["control"]["allowed_weekdays"]),
            },
            blocking=True,
        )
