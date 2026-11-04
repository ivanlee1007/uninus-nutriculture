"""Accepted native stage history survives global lifecycle changes."""

import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared, start_native
from test_p3_dosing_bounds import until
from test_p3_settings import apply, payload


def snapshot(hass, entry):
    return {
        "status_id": target(hass, entry, "sensor", "control_status"),
        "states": {
            s.entity_id: {"state": s.state, "attributes": dict(s.attributes)}
            for s in hass.states.async_all()
        },
    }


@pytest.mark.parametrize("outcome", ["aborted", "fault", "completed"])
async def test_native_terminal_history_and_shipped_reoperation(dosing_hass, tmp_path, outcome):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    control = entry.runtime_data.control
    pump, circ = hass.data["p3_fixture"]["outputs"]
    try:
        await start_native(hass, entry)
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        if outcome == "aborted":
            await toggle(hass, entry, "flow_run", False)
        elif outcome == "fault":
            hass.states.async_set("sensor.ec", "unavailable", {"unit_of_measurement": "mS/cm"})
            await until(lambda: not control.running)
            hass.states.async_set("sensor.ec", "0.85", {"unit_of_measurement": "mS/cm"})
            await hass.async_block_till_done()
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": target(hass, entry, "button", "reset_fault")},
                blocking=True,
            )
        else:
            hass.states.async_set("sensor.ec", "0.85", {"unit_of_measurement": "mS/cm"})
            await until(lambda: control.flow_state == "waiting_sample")
            hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
            await until(lambda: control.flow_state == "completed")
        assert not control.running and not control.nutrient_stage.owns_io
        assert not pump.is_on and not circ.is_on
        before_calls = list(hass.data["p3_fixture"]["calls"])
        data = payload(entry)
        data["parameters"]["ph_low"] = 5.4
        await apply(hass, data)
        await toggle(hass, entry, "automation_enabled", False)
        await hass.async_block_till_done()
        capture = snapshot(hass, entry)
        status = capture["states"][capture["status_id"]]
        assert status["state"] == "disabled"
        assert status["attributes"]["stage_states"]["nutrient"] == outcome
        assert control.run_stage == "nutrient"
        assert entry.options["control"]["automation_enabled"] is False
        assert hass.data["p3_fixture"]["calls"] == before_calls
        # Browser dependency is optional for the native suite; explicit bridge gate
        # uses the Card venv and unchanged shipped JS, never a handcrafted state.
        if os.environ.get("P3A_CARD_PYTHON"):
            root = Path(__file__).resolve().parents[1]
            capture_path = tmp_path / "native.json"
            capture_path.write_text(json.dumps(capture, default=str))
            proc = await asyncio.create_subprocess_exec(
                os.environ["P3A_CARD_PYTHON"],
                "-B",
                str(root / "tools/p3a_postrun_check.py"),
                str(capture_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), 30)
            print(stdout.decode(), stderr.decode())
            assert proc.returncode == 0
            commands = json.loads(stdout)["calls"]
            # Replay requests emitted by the actual shipped UI via registered Core
            # transport, then verify durable master/settings and no automatic ON.
            for domain, service, service_data in commands:
                await hass.services.async_call(domain, service, service_data, blocking=True)
            await hass.async_block_till_done()
            assert entry.options["control"]["automation_enabled"] is True
            assert entry.options["parameters"]["ph_low"] == 5.3
            assert not pump.is_on and not circ.is_on and not control.running
            assert hass.data["p3_fixture"]["calls"] == before_calls
        await toggle(hass, entry, "automation_enabled", True)
        assert not pump.is_on and not circ.is_on
        await start_native(hass, entry)
        await until(lambda: pump.is_on or circ.is_on)
        await toggle(hass, entry, "flow_run", False)
        assert not pump.is_on and not circ.is_on and not control.running
    finally:
        await control.stop()


async def test_pending_off_and_preentry_are_not_terminal_success(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    control = entry.runtime_data.control
    pump, _ = hass.data["p3_fixture"]["outputs"]
    try:
        await start_native(hass, entry)
        # Accepted background task may not have entered yet: never completed.
        status = snapshot(hass, entry)
        assert status["states"][status["status_id"]]["attributes"]["stage_states"]["nutrient"] in {
            "starting",
            "running",
        }
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        pump.off_ack_gate = asyncio.Event()
        stopper = asyncio.create_task(toggle(hass, entry, "flow_run", False))
        try:
            await asyncio.wait_for(pump.entered_off.wait(), 1)
            control.tank.publish()
            await asyncio.sleep(0)
            status = snapshot(hass, entry)
            assert control.running and control.nutrient_stage.owns_io
            assert status["states"][status["status_id"]]["attributes"]["stage_states"][
                "nutrient"
            ] not in {"completed", "aborted", "idle"}
        finally:
            pump.off_ack_gate.set()
            await asyncio.wait_for(stopper, 3)
    finally:
        await control.stop()
