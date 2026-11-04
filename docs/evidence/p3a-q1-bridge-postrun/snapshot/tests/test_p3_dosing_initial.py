"""Initial native admission must establish the selected measurement token."""

import asyncio
from datetime import timedelta

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native
from test_p3_dosing_bounds import until
from test_p3_settings import apply, payload


@pytest.mark.parametrize(
    "mode,token",
    [
        ("sequence", None),
        ("sequence", True),
        ("sequence", -1),
        ("timestamp", "future"),
        ("timestamp", "stale"),
        ("timestamp", "not-a-timestamp"),
    ],
)
async def test_initial_invalid_measurement_token_refuses_before_any_output(
    dosing_hass, mode, token
):
    hass = dosing_hass
    entry = await prepared(hass, sample_mode=mode, sample_attribute="sample")
    if token in ("future", "stale"):
        token = (dt_util.utcnow() + timedelta(days=1 if token == "future" else -1)).isoformat()
    hass.states.async_set("sensor.ec", "0.70", {"unit_of_measurement": "mS/cm", "sample": token})
    try:
        with pytest.raises(ServiceValidationError, match="sample_invalid"):
            await start_native(hass, entry)
        assert not hass.data["p3_fixture"]["calls"]
        assert not entry.runtime_data.control.running
        assert entry.runtime_data.control.run_id is None, (
            "Rejected admission must not invent a run identity"
        )
    finally:
        # If the old implementation wrongly accepted, let its owned task enter
        # before requesting cleanup; no fake started/output state is injected.
        await asyncio.sleep(0.03)
        await toggle(hass, entry, "flow_run", False)


async def test_explicit_next_run_uses_relaxed_new_settings_not_old_run_bounds(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, safe_min_level_m=2.1)
    pump, _ = hass.data["p3_fixture"]["outputs"]
    hass.states.async_set("sensor.level", "2.2", {"unit_of_measurement": "m"})
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    await toggle(hass, entry, "flow_run", False)
    assert not entry.runtime_data.control.running
    data = payload(entry)
    data["dosing_parameters"]["safe_min_level_m"] = 0.5
    await apply(hass, data)
    hass.states.async_set("sensor.level", "2.0", {"unit_of_measurement": "m"})
    pump.entered_on.clear()
    try:
        await start_native(hass, entry)
        await asyncio.wait_for(pump.entered_on.wait(), 1)
        assert hass.data["p3_fixture"]["calls"].count(("nutrient", "on")) == 2
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_native_nutrient_request_receipts_evict_after_64_actual_runs(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    control = entry.runtime_data.control
    hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
    run_ids = set()
    try:
        for index in range(65):
            result = await hass.services.async_call(
                "uninus_nutriculture",
                "start_flow",
                {"config_entry_id": entry.entry_id, "request_id": f"native-cache-{index}"},
                blocking=True,
                return_response=True,
            )
            assert result["accepted"] is True
            run_ids.add(result["run_id"])
            await until(lambda: control.nutrient_stage.phase == "waiting_sample")
            hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
            await until(lambda: not control.running)
        assert len(run_ids) == 65
        assert len(control.receipts) == 64
        assert "native-cache-0" not in control.receipts
        assert "native-cache-64" in control.receipts
        assert ("nutrient", "on") not in hass.data["p3_fixture"]["calls"]
    finally:
        await toggle(hass, entry, "flow_run", False)
