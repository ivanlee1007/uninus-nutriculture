"""Causal native readback/import race; no Core method or transport replacement."""

import asyncio
import contextlib
import importlib.util
import io
import json
import logging
import os
import subprocess
import sys
import threading
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHRASE = "was still running after final writes shutdown stage"


def test_readback_waits_for_real_platform_import(tmp_path):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("P3C_CAPTURE_DIR", None)
    for mode in ("--seed", "--worker"):
        _run_child(tmp_path, env, mode)
    raw = (tmp_path / "worker.log").read_text(encoding="utf-8")
    observed = json.loads((tmp_path / "observation.json").read_bytes())
    if output := os.environ.get("P5A_SETUP_EVIDENCE"):
        destination = Path(output)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "worker.log").write_text(raw, encoding="utf-8")
        (destination / "observation.json").write_text(json.dumps(observed, indent=2))
    assert observed["fresh_process"]
    assert observed["entry_loaded"] and observed["import_entered"]
    assert observed["closed"] and observed["import_thread_closed"]
    assert observed["canonical_equal"] and observed["service_calls"] == []
    assert observed["readback_before_import_complete"] is False, observed
    assert observed["shutdown_warning_count"] == 0, observed
    assert observed["checkpoint_before_readback"] is True, observed


def _run_child(tmp_path, env, mode):
    command = [sys.executable, "-B", str(Path(__file__).resolve()), mode, str(tmp_path)]
    log_path = tmp_path / (mode.removeprefix("--") + ".log")
    with log_path.open("wb") as log:
        child = subprocess.Popen(
            command,
            cwd=tmp_path,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        try:
            code = child.wait(timeout=60)
        finally:
            if child.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                    )
                else:
                    import signal

                    os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
    raw = log_path.read_text(encoding="utf-8")
    assert code == 0, raw


def _load_helper():
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    spec = importlib.util.spec_from_file_location(
        "p5a_fixture_under_test", ROOT / "tools/p5a_visual_native.py"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


async def _seed(directory):
    helper = _load_helper()
    base = helper.control_hass.__wrapped__(directory / "seed")
    seed = await anext(base)
    fixture = helper.dosing_hass.__wrapped__(seed)
    await anext(fixture)
    try:
        entry, _ = await helper.prepared(seed)
        await helper.save_v5(seed, entry)
        await asyncio.wait_for(seed.async_block_till_done(), 10)
        expected = helper.serial(dict(entry.options))
        await seed.config_entries._store.async_save(seed.config_entries._data_to_save())
        config_dir, entry_id = Path(seed.config.config_dir), entry.entry_id
    finally:
        await helper.stop_owned_core(seed)
        await fixture.aclose()
        await base.aclose()
    (directory / "seed-info.json").write_text(
        json.dumps(
            {
                "directory": str(config_dir),
                "entry_id": entry_id,
                "options": expected,
                "pid": os.getpid(),
            }
        )
    )


async def _worker(directory):
    helper = _load_helper()
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.const import EVENT_CALL_SERVICE, EVENT_HOMEASSISTANT_CLOSE
    from homeassistant.core import CoreState, callback
    from homeassistant.helpers.integration_platform import async_process_integration_platforms
    from homeassistant.loader import async_get_integration
    from homeassistant.setup import async_setup_component

    seed = json.loads((directory / "seed-info.json").read_bytes())
    config_dir = Path(seed["directory"])
    entry_id, expected = seed["entry_id"], seed["options"]
    gate = types.ModuleType("p5a_owned_import_gate")
    gate.release = threading.Event()
    gate.complete = threading.Event()
    gate.entered = asyncio.Event()
    gate.loop = asyncio.get_running_loop()
    sys.modules[gate.__name__] = gate
    probe = config_dir / "custom_components/p5a_owned_probe"
    probe.mkdir(parents=True)
    (probe / "manifest.json").write_text(
        json.dumps(
            {
                "domain": "p5a_owned_probe",
                "name": "Owned import barrier",
                "version": "1.0.0",
                "documentation": "https://example.invalid",
                "codeowners": [],
                "requirements": [],
            }
        )
    )
    (probe / "__init__.py").write_text("async def async_setup(hass, config):\n    return True\n")
    (probe / "p5a_barrier.py").write_text(
        "import p5a_owned_import_gate as gate\n"
        "gate.loop.call_soon_threadsafe(gate.entered.set)\n"
        "if not gate.release.wait(10):\n"
        "    raise RuntimeError('owned import barrier deadline')\n"
        "gate.complete.set()\n"
    )
    import custom_components

    custom_components.__path__.append(str(config_dir / "custom_components"))
    observed = {
        "fresh_process": seed["pid"] != os.getpid(),
        "entry_loaded": False,
        "import_entered": False,
        "readback_before_import_complete": None,
        "checkpoint_before_readback": False,
        "service_calls": [],
        "shutdown_warning_count": 0,
        "closed": False,
        "import_thread_closed": False,
        "canonical_equal": False,
        "helper_origin": str(ROOT / "tools/p5a_visual_native.py"),
    }
    created = []
    make = helper.make_hass
    capture = io.StringIO()

    class ReadbackCapture(io.StringIO):
        def write(self, value):
            if value.startswith('{"options":'):
                observed["readback_before_import_complete"] = not gate.complete.is_set()
            return super().write(value)

    capture = ReadbackCapture()

    class Warnings(logging.Handler):
        def emit(self, record):
            if PHRASE in record.getMessage():
                observed["shutdown_warning_count"] += 1

    warnings = Warnings()
    logging.getLogger("homeassistant.core").addHandler(warnings)

    async def owned_make(path):
        hass = await make(path)
        created.append(hass)

        @callback
        def close(_event):
            # In the predecessor the real CLOSE warning still sees the import Future.
            gate.release.set()

        @callback
        def service(event):
            observed["service_calls"].append(event.data["domain"])

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, close)
        hass.bus.async_listen(EVENT_CALL_SERVICE, service)
        # Leave the real entry NOT_LOADED, but warm its independent platform
        # imports before holding the single Core import-executor worker.
        platforms = ("number", "sensor", "switch", "button", "binary_sensor")
        for domain in platforms:
            assert await async_setup_component(hass, domain, {})
        integration = await async_get_integration(hass, "uninus_nutriculture")
        await integration.async_get_component()
        await integration.async_get_platforms(platforms)
        await asyncio.wait_for(hass.async_block_till_done(), 10)
        assert await async_setup_component(hass, "p5a_owned_probe", {})

        @callback
        def imported(_hass, domain, _platform):
            assert domain == "p5a_owned_probe"

        # Register after component setup so automatic preload cannot consume the
        # barrier inside async_setup_component. Core owns the real import Future.
        await async_process_integration_platforms(hass, "p5a_barrier", imported)
        await asyncio.wait_for(gate.entered.wait(), 10)
        observed["import_entered"] = True
        current = hass.config_entries.async_get_entry(entry_id)

        def checkpoint(remaining):
            if remaining:
                hass.loop.call_soon(checkpoint, remaining - 1)
                return
            observed["checkpoint_before_readback"] = (
                observed["readback_before_import_complete"] is None
            )
            if observed["checkpoint_before_readback"]:
                gate.release.set()

        @callback
        def state_changed():
            if current.state is ConfigEntryState.LOADED:
                observed["entry_loaded"] = True
                # A deterministic scheduling witness, not elapsed-time completion.
                # The old 20-turn yield can return; the real import remains held.
                hass.loop.call_soon(checkpoint, 64)

        current.async_on_state_change(state_changed)
        return hass

    helper.make_hass = owned_make  # Owned fixture factory, never a Core SDK method.
    try:
        with contextlib.redirect_stdout(capture):
            await asyncio.wait_for(helper.readback(config_dir, entry_id), 45)
        result = json.loads(capture.getvalue())
        observed["canonical_equal"] = (
            result["options"] == expected
            and result["entry_state"] == "loaded"
            and result["status"]["flow_plan"] == expected["flow_plan"]
            and result["status"]["allowed_weekdays"] == expected["control"]["allowed_weekdays"]
            and all(
                result["status"][key] == expected[key]
                for key in ("settings_revision", "flow_plan_revision")
            )
        )
        observed["closed"] = all(hass.state is CoreState.stopped for hass in created)
        observed["import_thread_closed"] = gate.complete.is_set()
    finally:
        gate.release.set()
        for hass in created:
            if hass.state is not CoreState.stopped:
                await helper.stop_owned_core(hass)
        logging.getLogger("homeassistant.core").removeHandler(warnings)
        (directory / "observation.json").write_text(json.dumps(observed, indent=2))
        sys.modules.pop(gate.__name__, None)


if __name__ == "__main__":
    operation = {"--seed": _seed, "--worker": _worker}[sys.argv[1]]
    asyncio.run(operation(Path(sys.argv[2])))
