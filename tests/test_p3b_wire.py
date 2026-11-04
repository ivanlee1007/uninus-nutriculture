"""Native schema4 -> shipped Chromium consumer -> native mutation roundtrip."""

import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_stage_projection import snapshot
from test_p3b_safety import acid_ready


def payload(hass, entry):
    a = hass.states.get(target(hass, entry, "sensor", "control_status")).attributes
    return {
        "config_entry_id": entry.entry_id,
        "expected_revision": a["settings_revision"],
        **{
            k: a[k]
            for k in (
                "parameters",
                "dosing_parameters",
                "acid_parameters",
                "mix_parameters",
                "safety_parameters",
                "allowed_weekdays",
            )
        },
    }


async def test_v4_native_cas_null_safety_atomic_and_bridge(dosing_hass, tmp_path):
    hass = dosing_hass
    entry = await acid_ready(hass)
    await toggle(hass, entry, "automation_enabled", False)
    data = payload(hass, entry)
    data["acid_parameters"] = {**data["acid_parameters"], "pulse_seconds": 1}
    response = await hass.services.async_call(
        "uninus_nutriculture",
        "apply_control_settings_v4",
        data,
        blocking=True,
        return_response=True,
    )
    assert response["applied"] and entry.options["acid_parameters"]["pulse_seconds"] == 1
    with pytest.raises(ServiceValidationError, match="settings_conflict"):
        await hass.services.async_call(
            "uninus_nutriculture", "apply_control_settings_v4", data, blocking=True
        )
    data = payload(hass, entry)
    data["acid_parameters"] = None
    before = dict(entry.options)
    with pytest.raises(ServiceValidationError, match="invalid_commissioning"):
        await hass.services.async_call(
            "uninus_nutriculture", "apply_control_settings_v4", data, blocking=True
        )
    assert dict(entry.options) == before
    if os.environ.get("P3B_CARD_PYTHON"):
        capture = tmp_path / "native.json"
        capture.write_text(json.dumps(snapshot(hass, entry), default=str))
        proc = await asyncio.create_subprocess_exec(
            os.environ["P3B_CARD_PYTHON"],
            str(Path(__file__).resolve().parents[1] / "tools/p3b_postrun_check.py"),
            str(capture),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), 30)
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.communicate()
        print(out.decode(), err.decode())
        assert proc.returncode == 0
        for domain, service, data in json.loads(out)["calls"]:
            await hass.services.async_call(domain, service, data, blocking=True)
        assert entry.options["parameters"]["ph_low"] == 5.3
        assert entry.runtime_data.control.master
        assert not hass.data["p3_fixture"]["calls"]


async def test_acid_emergency_without_run_closes_commissioned_outputs(dosing_hass):
    hass = dosing_hass
    entry = await acid_ready(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    for output in (pump, circ):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": output.entity_id}, blocking=True
        )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": target(hass, entry, "button", "emergency_stop")},
        blocking=True,
    )
    assert not pump.is_on and not circ.is_on
    assert entry.runtime_data.control.fault == "emergency_stop"
