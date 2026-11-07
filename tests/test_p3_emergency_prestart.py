"""Native emergency ownership before MixStage execution has a clock."""

import asyncio
import json
import os
from pathlib import Path

import pytest
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import call, plan, prepared, save_v5, settings_payload, until


@pytest.mark.parametrize("mix_enabled", [False, True])
async def test_native_accepted_prestart_emergency_closes(dosing_hass, caplog, mix_enabled):
    h = dosing_hass
    e, acid = await prepared(h)
    p = plan()
    for row in p["rows"]:
        row.update(start_rule="flow_start", delay_seconds=15)
    await save_v5(h, e, p)
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "refill_enabled")
    if mix_enabled:
        await toggle(h, e, "mix_enabled")
    c = e.runtime_data.control
    response = await start_native(h, e)
    assert response["accepted"] is True and response["run_id"]
    assert c.flow.active and c.mix_stage.task is None
    assert not any(hasattr(c.mix_stage, key) for key in ("started", "deadline", "end"))
    assert e.runtime_data.results.dto()["current_run"]["run_id"] == response["run_id"]
    try:
        await h.services.async_call(
            "button",
            "press",
            {"entity_id": target(h, e, "button", "emergency_stop")},
            blocking=True,
        )
        await until(lambda: e.runtime_data.results.dto()["last_result"] is not None)
        await h.async_block_till_done()
        assert c.fault == "emergency_stop" and not c.master
        assert not c.running and not c.flow.active and not c.flow.stopping
        assert h.states.get(target(h, e, "switch", "flow_run")).state == "off"
        outputs = [h.data["p2_fixture"]["hardware"], *h.data["p3_fixture"]["outputs"], acid]
        assert all(not output.is_on for output in outputs)
        assert ("nutrient", "off") in h.data["p3_fixture"]["calls"]
        assert ("circulation", "off") in h.data["p3_fixture"]["calls"]
        assert not c.leases
        for name in ("refill", "nutrient", "acid", "mix"):
            stage = c.flow.stage(name)
            assert not stage.owns_io
            assert all(op.done() for op in stage.operations.values())
            assert stage.task is None or stage.task.done()
        dto = e.runtime_data.results.dto()
        assert dto["current_run"] is None
        assert (
            dto["last_result"]["state"],
            dto["last_result"]["reason"],
            dto["last_result"]["closure"],
        ) == ("failed", "emergency_stop", "confirmed")
        assert not e.runtime_data.quality.granted
        assert not [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
    finally:
        # Read-only diagnostic survives the genuine native exception in RED.
        directory = os.environ.get("P3C_CAPTURE_DIR")
        if directory:
            out = Path(directory)
            out.mkdir(parents=True, exist_ok=True)
            (out / f"prestart-{mix_enabled}.json").write_text(
                json.dumps(
                    {
                        "response": response,
                        "result": e.runtime_data.results.dto(),
                        "flow_active": c.flow.active,
                        "flow_stopping": c.flow.stopping,
                        "fault": c.fault,
                        "leases": list(c.leases),
                        "owners": {
                            s: c.flow.stage(s).owns_io
                            for s in ("refill", "nutrient", "acid", "mix")
                        },
                        "errors": [
                            r.getMessage() for r in caplog.records if r.levelname == "ERROR"
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )


@pytest.mark.parametrize("started", [False, True])
async def test_mix_execution_tightening_and_emergency_off_ack(dosing_hass, caplog, started):
    """Supplementary safety coverage, not an additional behavioral RED claim."""
    h = dosing_hass
    e, _ = await prepared(h)
    p = plan()
    for row in p["rows"]:
        row.update(start_rule="flow_start", delay_seconds=0 if started else 15)
    await save_v5(h, e, p)
    h.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await h.services.async_call(
        "number",
        "set_value",
        {"entity_id": target(h, e, "number", "mix_duration"), "value": 3},
        blocking=True,
    )
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "mix_enabled")
    c = e.runtime_data.control
    mix = c.mix_stage
    circ = h.data["p3_fixture"]["outputs"][1]
    assert (await start_native(h, e))["accepted"] is True
    if started:
        await asyncio.wait_for(circ.entered_on.wait(), 2)
        assert mix.task is not None and not mix.task.done() and mix.owns_io
        assert c.leases
        old_deadline, old_end = mix.deadline, mix.end
        payload = settings_payload(e)
        payload["mix_parameters"] = {**payload["mix_parameters"], "flow_timeout_seconds": 300}
        payload["parameters"] = {**e.runtime_data.parameters, "mix_duration": 1}
        await call(h, "apply_control_settings_v5", payload)
        assert mix.deadline == mix.started + 300 < old_deadline
        assert mix.end == mix.started + 60 < old_end
        tight = mix.deadline, mix.end
        payload = settings_payload(e)
        payload["mix_parameters"] = {**payload["mix_parameters"], "flow_timeout_seconds": 900}
        payload["parameters"] = {**e.runtime_data.parameters, "mix_duration": 2}
        await call(h, "apply_control_settings_v5", payload)
        assert (mix.deadline, mix.end) == tight
    else:
        assert mix.task is None and not hasattr(mix, "deadline")
    gate = asyncio.Event()
    circ.off_ack_gate = gate
    request = asyncio.create_task(
        h.services.async_call(
            "button",
            "press",
            {"entity_id": target(h, e, "button", "emergency_stop")},
            blocking=True,
        )
    )
    try:
        await asyncio.wait_for(circ.entered_off.wait(), 0.75)
        await until(lambda: any(not op.done() for op in mix.operations.values()), seconds=0.75)
        await asyncio.sleep(0.05)
        assert not circ.is_on and not gate.is_set()
        assert mix.owns_io and c.running and not request.done()
        assert c.flow.active and c.flow.stopping
        assert e.runtime_data.results.dto()["last_result"] is None
        assert e.runtime_data.results.dto()["current_run"] is not None
        assert c.fault == "emergency_stop" and not c.master
    finally:
        gate.set()
        await asyncio.wait_for(request, 4)
    await until(lambda: e.runtime_data.results.dto()["last_result"] is not None)
    assert not c.running and not c.leases and not c.flow.active and not c.flow.stopping
    assert not mix.owns_io and all(op.done() for op in mix.operations.values())
    assert h.states.get(target(h, e, "switch", "flow_run")).state == "off"
    result = e.runtime_data.results.dto()["last_result"]
    assert (result["state"], result["reason"], result["closure"]) == (
        "failed",
        "emergency_stop",
        "confirmed",
    )
    assert not [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
