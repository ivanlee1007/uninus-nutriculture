"""Native diagnostics stay private while fault latch and cleanup stay truthful."""

import asyncio

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native
from test_p3_dosing_bounds import until


@pytest.mark.parametrize(
    ("error_type", "diagnostic"),
    [
        (RuntimeError, "FICTITIOUS_TOKEN=not-a-real-secret; " + "x" * 4096),
        (ServiceValidationError, "FICTITIOUS_TOKEN=not-a-real-secret"),
        (ServiceValidationError, "source_invalid:FICTITIOUS_TOKEN=not-a-real-secret"),
    ],
)
async def test_unknown_provider_fault_is_closed_and_still_locked(
    dosing_hass, error_type, diagnostic
):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, circulation = hass.data["p3_fixture"]["outputs"]

    async def fail_provider(**kwargs):
        pump.entered_on.set()
        raise error_type(diagnostic)

    pump.async_turn_on = fail_provider
    control = entry.runtime_data.control
    try:
        receipt = await start_native(hass, entry)
        assert receipt["accepted"]
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        await until(lambda: control.nutrient_stage.task.done())
        await hass.async_block_till_done()
        status = hass.states.get(target(hass, entry, "sensor", "control_status"))
        assert control.fault == "operation_failed"
        assert entry.options["control"]["fault"] == "operation_failed"
        assert status.attributes["fault"] == "operation_failed"
        assert status.state == "fault"
        assert not control.master and not control.running
        assert not pump.is_on and not circulation.is_on
        assert ("nutrient", "off") in hass.data["p3_fixture"]["calls"]
        assert ("circulation", "off") in hass.data["p3_fixture"]["calls"]
        with pytest.raises(ServiceValidationError, match="fault_latched"):
            await toggle(hass, entry, "automation_enabled")
    finally:
        await control.stop()


async def test_legacy_persisted_diagnostic_is_closed_on_native_reload(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    config = dict(entry.options["control"])
    config.update(fault="FICTITIOUS_TOKEN=not-a-real-secret", automation_enabled=True)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "control": config})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    control = entry.runtime_data.control
    status = hass.states.get(target(hass, entry, "sensor", "control_status"))
    assert control.fault == "operation_failed"
    assert entry.options["control"]["fault"] == "operation_failed"
    assert status.attributes["fault"] == "operation_failed"
    assert status.state == "fault" and not control.master


@pytest.mark.parametrize("code", ["ec_timeout", "source_invalid", "stop_unconfirmed"])
async def test_existing_domain_fault_codes_remain_exact(dosing_hass, code):
    hass = dosing_hass
    entry = await prepared(hass)
    entry.runtime_data.control.fault = code
    entry.runtime_data.publish()
    await hass.async_block_till_done()
    assert entry.runtime_data.control.fault == code
    assert entry.options["control"]["fault"] == code
    status = hass.states.get(target(hass, entry, "sensor", "control_status"))
    assert status.attributes["fault"] == code
