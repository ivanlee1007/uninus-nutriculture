"""Real SDK cleanup observations are captured before any test rescue."""

import asyncio
import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest
from homeassistant.core import CoreState, HomeAssistant


@pytest.mark.parametrize("fault", ["wire", "early", "spawn", "readback"])
async def test_owned_core_stops_after_failure(tmp_path, monkeypatch, fault):
    root = Path(__file__).resolve().parents[1]
    source = root / "tools" / "p5a_visual_native.py"
    old_path = sys.path[:]
    name = "owned_cleanup_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, source)
    helper = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(helper)
    finally:
        sys.path[:] = old_path
    import p2_fixtures

    assert Path(p2_fixtures.__file__).resolve().is_relative_to(root)
    output = tmp_path / "owned-output"
    monkeypatch.setenv("P5A_JOIN_OUTPUT", str(output))
    monkeypatch.setenv("P5A_CARD_PYTHON", sys.executable)
    monkeypatch.delenv("P3C_CAPTURE_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", [str(source), "fault", *([] if fault == "spawn" else ["--smoke"])]
    )
    created, stops, children, replies = [], [], [], []
    make = p2_fixtures.make_hass
    stop = HomeAssistant.async_stop
    write = helper.write
    spawn = asyncio.create_subprocess_exec
    error = OSError(
        "QUALITY_INJECTED_CAPTURE_WRITE_FAILURE" if fault == "wire" else "OWNED_" + fault
    )

    async def observe_make(directory):
        hass = await make(directory)
        created.append(hass)
        return hass

    async def observe_stop(hass, *args, **kwargs):
        stops.append(id(hass))
        return await stop(hass, *args, **kwargs)

    def capture(path, value):
        if path.name == "wire.json":
            replies.extend(value)
            raise error
        return write(path, value)

    async def fail_early(hass):
        raise error

    async def failed_child(*args, **kwargs):
        child = await spawn(sys.executable, "-B", "-c", "import time; time.sleep(60)", **kwargs)
        children.append(child)
        # A real owned child exists before its stdout fails framing.
        child.stdout.feed_data(b"not-json\n")
        return child

    monkeypatch.setattr(HomeAssistant, "async_stop", observe_stop)
    monkeypatch.setattr(p2_fixtures, "make_hass", observe_make)
    if fault == "wire":
        monkeypatch.setattr(helper, "write", capture)
    elif fault == "early":
        monkeypatch.setattr(helper, "prepared", fail_early)
    elif fault == "spawn":
        monkeypatch.setattr(helper.asyncio, "create_subprocess_exec", failed_child)
    else:
        monkeypatch.setattr(helper, "make_hass", observe_make)
    caught = None
    try:
        try:
            if fault == "readback":
                await helper.readback(tmp_path / "readback", "missing-entry")
            else:
                await helper.main()
        except BaseException as exc:
            caught = exc
        observed = {
            "candidate_stops": stops[:],
            "states": [h.state.value for h in created],
            "child_codes": [child.returncode for child in children],
            "caught": repr(caught),
            "helper_origin": str(source),
        }
        (tmp_path / "candidate-observation.json").write_text(json.dumps(observed, indent=2))
        assert created
        if fault == "wire":
            assert len(replies) == 1 and replies[0]["reply"]["success"]
            assert replies[0]["reply"]["result"]["response"]["weekday"] == "mon"
        if fault in ("wire", "early"):
            assert caught is error
        elif fault == "spawn":
            assert isinstance(caught, json.JSONDecodeError)
        else:
            assert isinstance(caught, AssertionError)
        assert all(child.returncode is not None for child in children)
        assert all(id(hass) in observed["candidate_stops"] for hass in created)
        assert all(hass.state is CoreState.stopped for hass in created)
    finally:
        # Rescue is deliberately outside the recorded candidate assertion evidence.
        for child in children:
            if child.returncode is None:
                child.kill()
            await asyncio.wait_for(child.communicate(), 10)
        for hass in created:
            if hass.state is not CoreState.stopped:
                await asyncio.wait_for(stop(hass, force=True), 10)
        sys.modules.pop(name, None)
