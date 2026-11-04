"""Real accepted role terminals remain consumable after zero-I/O settings/reset."""

import asyncio
import json
import os
from pathlib import Path

import pytest
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3_stage_projection import snapshot
from test_p3b_remaining import mix_ready
from test_p3b_safety import acid_ready


@pytest.mark.parametrize("role", ["acid", "mix"])
async def test_real_role_terminal_settings_shipped_consumer(dosing_hass, tmp_path, role):
    hass = dosing_hass
    entry = await (acid_ready(hass) if role == "acid" else mix_ready(hass))
    pump, circ = hass.data["p3_fixture"]["outputs"]
    stage = getattr(entry.runtime_data.control, role + "_stage")
    clock = stage.clock
    for index, ending in enumerate(("aborted", "fault", "completed")):
        hass.states.async_set("sensor.ph", "6.5", {"sample": index * 10 + 2})
        hass.states.async_set("sensor.ec", ".85", {"unit_of_measurement": "mS/cm"})
        await toggle(hass, entry, "automation_enabled")
        await toggle(hass, entry, role + "_enabled")
        pump.entered_on.clear()
        circ.entered_on.clear()
        await start_native(hass, entry)
        await asyncio.wait_for((pump if role == "acid" else circ).entered_on.wait(), 2)
        if ending == "aborted":
            await toggle(hass, entry, "flow_run", False)
        elif ending == "fault":
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": target(hass, entry, "button", "emergency_stop")},
                blocking=True,
            )
        elif role == "mix":
            now = clock()
            stage.clock = lambda: now + 61  # domain clock seam, native 1 min Number unmodified
            stage.wake.set()
        else:
            hass.states.async_set(
                "sensor.ph",
                str(entry.runtime_data.parameters["ph_low"]),
                {"sample": index * 10 + 3},
            )
            async with asyncio.timeout(3):
                while entry.runtime_data.control.flow_state != "waiting_sample":
                    await asyncio.sleep(0.01)
            hass.states.async_set(
                "sensor.ph",
                str(entry.runtime_data.parameters["ph_low"]),
                {"sample": index * 10 + 4},
            )
        async with asyncio.timeout(3):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        stage.clock = clock
        assert stage.result == ending
        await toggle(hass, entry, "automation_enabled", False)
        if ending == "fault":
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": target(hass, entry, "button", "reset_fault")},
                blocking=True,
            )
        assert (
            hass.states.get(target(hass, entry, "sensor", "control_status")).attributes[
                "stage_states"
            ][role]
            == ending
        )
        count = len(hass.data["p3_fixture"]["calls"])
        if os.environ.get("P3B_CARD_PYTHON"):
            capture = tmp_path / (role + "-" + ending + ".json")
            capture.write_text(json.dumps(snapshot(hass, entry), default=str))
            proc = await asyncio.create_subprocess_exec(
                os.environ["P3B_CARD_PYTHON"],
                str(Path(__file__).resolve().parents[1] / "tools/p3b_postrun_check.py"),
                str(capture),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(proc.communicate(), 30)
            finally:
                if proc.returncode is None:
                    proc.kill()
                    await proc.communicate()
            print(role, ending, out.decode(), err.decode())
            assert proc.returncode == 0
            for domain, service, data in json.loads(out)["calls"]:
                await hass.services.async_call(domain, service, data, blocking=True)
            assert entry.runtime_data.control.master
            assert (
                hass.states.get(target(hass, entry, "sensor", "control_status")).attributes[
                    "stage_states"
                ][role]
                == ending
            )
        assert len(hass.data["p3_fixture"]["calls"]) == count, (
            "Enable / Apply / reset must never auto-ON"
        )
        await toggle(hass, entry, "automation_enabled", False)
