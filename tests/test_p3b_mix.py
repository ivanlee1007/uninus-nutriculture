"""Native standalone bounded circulation, no dosing-source dependency."""

import asyncio

import pytest
from homeassistant.data_entry_flow import FlowResultType
from test_p2_control import add_tank, target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native


@pytest.mark.parametrize("entrance", ["service", "switch"])
async def test_standalone_options_enable_bounded_off_unknown_quality(dosing_hass, entrance):
    hass = dosing_hass
    entry = await add_tank(hass)
    # Native Number determines requested mixing duration; no direct runtime mutation.
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": target(hass, entry, "number", "mix_duration"), "value": 1},
        blocking=True,
    )
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    values = dict(
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
        circulation_alias_notes="Fixture cutoff only",
    )
    result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert result["type"] == FlowResultType.CREATE_ENTRY, result
    assert entry.options.get("mix_parameters") == {
        "safe_min_level_m": 0.5,
        "flow_timeout_seconds": 120,
    }
    hass.states.async_set("sensor.ph", "unavailable")
    hass.states.async_set("sensor.ec", "unavailable")
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    assert not hass.data["p3_fixture"]["calls"]
    pump, circ = hass.data["p3_fixture"]["outputs"]
    try:
        if entrance == "service":
            await start_native(hass, entry)
        else:
            await toggle(hass, entry, "flow_run")
        await asyncio.wait_for(circ.entered_on.wait(), 2)
        assert not pump.is_on
        stage = entry.runtime_data.control.mix_stage
        now = stage.clock()
        stage.clock = lambda: now + 61
        stage.wake.set()
        await asyncio.wait_for(circ.entered_off.wait(), 1)
        async with asyncio.timeout(2):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert entry.runtime_data.control.flow_state == "completed"
        assert not circ.is_on
        assert ("nutrient", "on") not in hass.data["p3_fixture"]["calls"]
        status = hass.states.get(target(hass, entry, "sensor", "control_status")).attributes
        assert status["capabilities"]["mix"] is True
        assert status["stage_states"]["mix"] == "completed"
    finally:
        await toggle(hass, entry, "flow_run", False)
