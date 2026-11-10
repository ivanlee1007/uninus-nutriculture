# ruff: noqa: E402
"""Owned P5a native join. Required: P5A_JOIN_OUTPUT, P5A_CARD_PYTHON.

Run with backend SDK Python: -B tools/p5a_visual_native.py attempt-name
--smoke runs native Store/Options/fresh-process checks, NOT visual acceptance.
--readback CONFIG_DIR ENTRY_ID is the same-file fresh SDK child entry point.
All runtime and evidence writes belong under P5A_JOIN_OUTPUT, outside sources.
"""

import asyncio
import hashlib
import importlib.metadata
import json
import logging
import os
import sys
import traceback
from pathlib import Path

import homeassistant  # noqa: F401

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
CARD = ROOT.parent / "uninus-nutriculture-card"
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from conftest import make_hass
from homeassistant.auth import auth_manager_from_config
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.websocket_api import async_register_command, commands
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.storage import Store
from p2_fixtures import control_hass
from test_p2_control import target
from test_p3_dosing import dosing_hass
from test_p3_stage_projection import snapshot
from test_p3c_flow import DAYS, prepared, save_v5
from test_p3c_spec_fixes import suggested

logging.basicConfig(level=logging.WARNING)


def serial(value):
    return json.loads(json_bytes(value))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(serial(value), ensure_ascii=False, indent=2), encoding="utf-8")


def inventory():
    return {
        f.relative_to(ROOT.parent).as_posix(): digest(f.read_bytes())
        for root in (ROOT, CARD)
        for f in root.rglob("*")
        if f.is_file()
    }


async def barrier():
    for _ in range(20):
        await asyncio.sleep(0)


async def stop_owned_core(hass):
    """Bound the real Core lifecycle, not just async-generator closure."""
    from homeassistant.core import CoreState

    if hass is not None and hass.state is not CoreState.stopped:
        await asyncio.wait_for(hass.async_stop(force=True), 10)


async def cleanup_owned(hass, fixture, base, child, drain):
    """Keep every owned teardown independent, retaining the first failure."""
    errors = []

    async def attempt(operation):
        try:
            await asyncio.wait_for(operation(), 10)
        except BaseException as error:
            errors.append(error)
            traceback.print_exc(file=sys.stderr)

    # Stop while hardware fixtures and their acknowledgement callbacks still exist.
    await attempt(lambda: stop_owned_core(hass))
    if child is not None:

        async def close_child():
            if child.returncode is None:
                child.kill()
            await child.wait()

        await attempt(close_child)
        if child.stdin is not None:
            try:
                child.stdin.close()
            except Exception as error:
                errors.append(error)
                traceback.print_exc(file=sys.stderr)
        await attempt(child.stdout.read)
        if drain is None:
            await attempt(child.stderr.read)
    if drain is not None:
        await attempt(lambda: drain)
    if fixture is not None:
        await attempt(fixture.aclose)
    await attempt(base.aclose)
    return errors


async def readback(directory, entry_id):
    """Real ConfigEntries load + external telemetry before canonical setup."""
    hass = await make_hass(directory)
    try:
        entry = hass.config_entries.async_get_entry(entry_id)
        assert entry is not None
        before = serial(dict(entry.options))
        from homeassistant.helpers import entity_registry as er

        outputs = []
        for row in er.async_get(hass).entities.values():
            if row.entity_id.startswith("switch.") and row.platform == "switch":
                hass.states.async_set(row.entity_id, "off")
                outputs.append(row.entity_id)
        assert len(outputs) == 4, outputs
        for key, value, unit in (("ph", 5.6, "pH"), ("ec", 0.85, "mS/cm"), ("level", 2, "m")):
            hass.states.async_set("sensor." + key, value, {"unit_of_measurement": unit})
        assert await hass.config_entries.async_setup(entry.entry_id)
        # Entry LOADED does not drain component-loaded platform imports. Unlike
        # fixed loop turns, Core's public barrier waits for tracked setup work
        # (not background tasks), inside the existing owned lifecycle budget.
        await asyncio.wait_for(hass.async_block_till_done(), 10)
        assert serial(dict(entry.options)) == before
        status = hass.states.get(target(hass, entry, "sensor", "control_status"))
        attr = serial(dict(status.attributes))
        assert attr["flow_plan"] == before["flow_plan"]
        assert attr["allowed_weekdays"] == before["control"]["allowed_weekdays"]
        for key in ("flow_plan_revision", "settings_revision"):
            assert attr[key] == before[key]
        assert attr["flow_plan_target"]["config_entry_id"] == entry.entry_id
        print(
            json.dumps(
                {
                    "options": before,
                    "status": attr,
                    "status_id": status.entity_id,
                    "entry_state": entry.state.value,
                    "pid": os.getpid(),
                }
            ),
            flush=True,
        )
    finally:
        original_error = sys.exc_info()[1]
        try:
            await stop_owned_core(hass)
        except BaseException:
            if original_error is None:
                raise
            traceback.print_exc(file=sys.stderr)


async def main():
    out = Path(os.environ["P5A_JOIN_OUTPUT"]).resolve()
    assert not out.is_relative_to(ROOT) and not out.is_relative_to(CARD)
    out.mkdir(parents=True, exist_ok=True)
    os.chdir(out)
    # Legacy capture is optional and must never resolve to a source directory.
    if capture := os.environ.get("P3C_CAPTURE_DIR"):
        assert Path(capture).resolve().is_relative_to(out)
    attempt = sys.argv[1] if len(sys.argv) > 1 else "attempt1"
    assert Path(attempt).name == attempt and attempt not in (".", "..")
    smoke_only = "--smoke" in sys.argv
    run = out / attempt
    run.mkdir(exist_ok=False)
    before_sources = inventory()
    write(run / "source-before.json", before_sources)
    for relative in before_sources:
        source = ROOT.parent / relative
        destination = run / "source-bytes" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    command = [os.environ["P5A_CARD_PYTHON"], "-B", str(TOOLS / "p5a_visual_browser.py")]
    write(
        run / "command.json",
        {
            "parent": [sys.executable, "-B", str(Path(__file__).resolve()), *sys.argv[1:]],
            "child": command,
            "cwd": str(out),
            "core": importlib.metadata.version("homeassistant"),
            "python": sys.version,
            "env": {
                key: os.environ.get(key)
                for key in (
                    "P5A_JOIN_OUTPUT",
                    "P5A_CARD_PYTHON",
                    "PYTHONPATH",
                    "PYTHONDONTWRITEBYTECODE",
                    "CHROMIUM_EXECUTABLE",
                    "NODE",
                    "P3C_CAPTURE_DIR",
                )
            },
            "second_slot": "not exercised; no multi-slot acceptance",
        },
    )
    write(
        out / "CHECKPOINT.json",
        {"state": "callable_running", "attempt": str(run), "smoke_only": smoke_only},
    )
    base = control_hass.__wrapped__(run)
    fixture = None
    child = None
    drain = None
    hass = None
    events, wire, commits = [], [], []
    failure = None
    child_code = None
    try:
        hass = await anext(base)
        fixture = dosing_hass.__wrapped__(hass)
        await anext(fixture)
        entry, acid = await prepared(hass)
        await save_v5(hass, entry)
        await barrier()
        assert entry.options["control_contract_version"] == 5
        dr.async_get(hass)
        hass.auth = await auth_manager_from_config(hass, [], [])
        await hass.auth.async_create_user("Owned P5a owner")
        user = await hass.auth.async_create_user("Owned P5a admin", group_ids=[GROUP_ID_ADMIN])
        assert not user.is_owner and user.is_admin and user.is_active
        async_register_command(hass, commands.handle_call_service)
        future = None
        transport_id = 0

        def send(message):
            if isinstance(message, (bytes, str)):
                message = json.loads(message)
            if future and not future.done():
                future.set_result(serial(message))

        conn = ActiveConnection(
            logging.getLogger("owned.p5a.connection"), hass, send, user, None, None
        )

        async def observe(_hass, updated):
            commits.append(serial(dict(updated.options)))

        entry.add_update_listener(observe)

        async def open_plan(_hass, _entry):
            form = await hass.config_entries.options.async_init(
                entry.entry_id, context={"user_id": user.id}
            )
            return await hass.config_entries.options.async_configure(
                form["flow_id"], {"flow_plan": True}
            )

        def snap():
            return {
                **snapshot(hass, entry),
                "user_id": user.id,
                "services": {
                    domain: {name: {} for name in values}
                    for domain, values in hass.services.async_services().items()
                },
            }

        def io():
            return serial(
                {
                    "refill": hass.data["p2_fixture"]["calls"],
                    "dosing": hass.data["p3_fixture"]["calls"],
                    "acid_on": acid.is_on,
                }
            )

        async def stored():
            store = hass.config_entries._store
            await store.async_save(hass.config_entries._data_to_save())
            data = await Store(
                hass, store.version, store.key, minor_version=store.minor_version
            ).async_load()
            row = next(row for row in data["entries"] if row["entry_id"] == entry.entry_id)
            assert row["options"] == serial(dict(entry.options))
            return {"options": row["options"], "store_key": store.key}

        async def inspect():
            await barrier()
            await stored()
            disk = Path(hass.config.path(".storage/core.config_entries"))
            return {
                "options": dict(entry.options),
                "snapshot": snap(),
                "io": io(),
                "commit_count": len(commits),
                "disk": digest(disk.read_bytes()),
            }

        async def native(message, principal_id):
            nonlocal future, transport_id
            assert principal_id == user.id, "principal must match real ActiveConnection"
            assert await hass.auth.async_get_user(principal_id) is user
            transport_id += 1
            request = {**message, "id": transport_id}
            assert {k: v for k, v in request.items() if k != "id"} == message
            future = asyncio.get_running_loop().create_future()
            conn.async_handle(request)
            reply = await asyncio.wait_for(future, 15)
            await barrier()
            wire.append(
                {
                    "emitted": message,
                    "request": request,
                    "reply": reply,
                    "options": dict(entry.options),
                    "io": io(),
                    "commit_count": len(commits),
                }
            )
            write(run / "wire.json", wire)
            return {"reply": reply, "snapshot": snap()}

        held_form = None

        async def action(kind, payload):
            nonlocal held_form
            if kind == "snapshot":
                return {"snapshot": snap()}
            if kind == "inspect":
                return await inspect()
            if kind == "ws":
                return await native(payload["message"], payload["principal_id"])
            if kind == "smoke_registered":
                result = await native(
                    {
                        "type": "call_service",
                        "domain": "uninus_nutriculture",
                        "service": "preview_flow_plan_v5",
                        "return_response": True,
                        "service_data": {
                            "config_entry_id": entry.entry_id,
                            "expected_revision": entry.options["settings_revision"],
                            "expected_flow_plan_revision": entry.options["flow_plan_revision"],
                            "flow_plan": entry.options["flow_plan"],
                            "allowed_weekdays": entry.options["control"]["allowed_weekdays"],
                            "weekday": "mon",
                        },
                    },
                    user.id,
                )
                assert result["reply"]["success"], result
                assert result["reply"]["result"]["response"]["weekday"] == "mon"
                return result
            if kind == "options_preview_cancel":
                before = await inspect()
                form = await open_plan(hass, entry)
                values = suggested(form)
                assert len(values) == 34, values
                values["action"] = "preview"
                form = await hass.config_entries.options.async_configure(form["flow_id"], values)
                assert form["type"] == "form" and form["step_id"] == "plan", form
                assert form["description_placeholders"]["preview"].count(":") == 7
                values["action"] = "cancel"
                result = await hass.config_entries.options.async_configure(form["flow_id"], values)
                assert result["type"] == "abort"
                after = await inspect()
                for key in ("options", "io", "commit_count", "disk"):
                    assert before[key] == after[key], key
                write(run / "options-preview-cancel.json", {"before": before, "after": after})
                return after
            if kind == "options_hold":
                held_form = await open_plan(hass, entry)
                return {"suggested": suggested(held_form)}
            if kind == "smoke_advance":
                assert smoke_only
                plan = serial(entry.options["flow_plan"])
                plan["rows"][-1]["delay_seconds"] += 1
                result = await native(
                    {
                        "type": "call_service",
                        "domain": "uninus_nutriculture",
                        "service": "apply_flow_plan_v5",
                        "return_response": True,
                        "service_data": {
                            "config_entry_id": entry.entry_id,
                            "expected_revision": entry.options["settings_revision"],
                            "expected_flow_plan_revision": entry.options["flow_plan_revision"],
                            "flow_plan": plan,
                            "allowed_weekdays": entry.options["control"]["allowed_weekdays"],
                        },
                    },
                    user.id,
                )
                assert result["reply"]["success"], result
                return result
            if kind == "options_stale":
                assert held_form is not None
                before = await inspect()
                result = await hass.config_entries.options.async_configure(
                    held_form["flow_id"], suggested(held_form)
                )
                assert result["errors"]["base"] == "settings_conflict", result
                hass.config_entries.options.async_abort(held_form["flow_id"])
                held_form = None
                after = await inspect()
                for key in ("options", "io", "commit_count", "disk"):
                    assert before[key] == after[key], key
                write(
                    run / "options-stale.json",
                    {"before": before, "after": after, "errors": result["errors"]},
                )
                return after
            if kind == "options_save":
                before = await inspect()
                form = await open_plan(hass, entry)
                values = suggested(form)
                stages = [values[f"row_{i}_stage"] for i in range(4)]
                key = f"row_{stages.index('acid')}_weekdays"
                values[key] = list(DAYS) if "sun" not in values[key] else list(DAYS[:-1])
                values["action"] = "save"
                result = await hass.config_entries.options.async_configure(form["flow_id"], values)
                assert result["type"] == "create_entry", result
                after = await inspect()
                expected = serial(before["options"])
                expected["control"]["allowed_weekdays"]["acid"] = values[key]
                for revision in ("settings_revision", "flow_plan_revision"):
                    expected[revision] += 1
                assert after["options"] == expected
                assert after["commit_count"] == before["commit_count"] + 1
                assert after["io"] == before["io"]
                write(run / "options-save.json", {"before": before, "after": after})
                return after
            if kind == "store_readback":
                result = await stored()
                write(run / "fresh-store-readback.json", result)
                return result
            if kind == "fresh_sdk":
                expected = serial(dict(entry.options))
                await stored()
                config_dir = hass.config.config_dir
                await hass.async_stop(force=True)
                fresh = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-B",
                    str(Path(__file__).resolve()),
                    "--readback",
                    config_dir,
                    entry.entry_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=out,
                    limit=8 * 1024 * 1024,
                )
                stdout = stderr = b""
                try:
                    stdout, stderr = await asyncio.wait_for(fresh.communicate(), 45)
                finally:
                    if fresh.returncode is None:
                        fresh.kill()
                        stdout, stderr = await asyncio.wait_for(fresh.communicate(), 10)
                    (run / "fresh.stdout.jsonl").write_bytes(stdout)
                    (run / "fresh.stderr.log").write_bytes(stderr)
                    write(
                        run / "fresh-exit.json", {"exit_code": fresh.returncode, "pid": fresh.pid}
                    )
                assert fresh.returncode == 0
                result = json.loads(stdout)
                assert result["options"] == expected
                assert result["pid"] != os.getpid()
                write(run / "fresh-sdk-readback.json", result)
                return result
            if kind in ("checkpoint", "done"):
                events.append({"kind": kind, **payload})
                write(run / "events.json", events)
                write(
                    out / "CHECKPOINT.json",
                    {"state": "running", "attempt": str(run), "events": events},
                )
                return {}
            raise ValueError(kind)

        if smoke_only:
            for kind in (
                "smoke_registered",
                "options_preview_cancel",
                "options_hold",
                "smoke_advance",
                "options_stale",
                "options_save",
                "store_readback",
                "fresh_sdk",
            ):
                if kind == "fresh_sdk":
                    async with asyncio.timeout(60):
                        await action(kind, None)
                else:
                    await action(kind, None)
                events.append({"case": kind, "smoke_only": True})
            child_code = 0
        else:
            child = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=out,
                limit=8 * 1024 * 1024,
            )

            async def drain_stderr():
                with (run / "browser.stderr.log").open("wb") as stream:
                    while data := await child.stderr.read(65536):
                        stream.write(data)

            drain = asyncio.create_task(drain_stderr())
            async with asyncio.timeout(300):
                while line := await asyncio.wait_for(child.stdout.readline(), 15):
                    with (run / "ipc.raw.jsonl").open("ab") as stream:
                        stream.write(line)
                    message = json.loads(line)
                    try:
                        if message["kind"] == "fresh_sdk":
                            # Cancellation deadline; owned cleanup still completes before reply.
                            async with asyncio.timeout(60):
                                result = await action(message["kind"], message.get("payload"))
                        else:
                            result = await action(message["kind"], message.get("payload"))
                    except Exception as error:
                        traceback.print_exc(file=sys.stderr)
                        result = {"harness_error": f"{type(error).__name__}: {error}"}
                        failure = result["harness_error"]
                    response = json_bytes(result) + b"\n"
                    with (run / "ipc-replies.raw.jsonl").open("ab") as stream:
                        stream.write(response)
                    child.stdin.write(response)
                    await child.stdin.drain()
                child_code = await asyncio.wait_for(child.wait(), 10)
                await asyncio.wait_for(drain, 10)
            if child_code != 0:
                raise RuntimeError("browser behavioral assertion failed; inspect owned stderr")
            assert events and events[-1]["kind"] == "done"
        if failure:
            raise RuntimeError(failure)
    except BaseException as error:
        failure = f"{type(error).__name__}: {error}"
        raise
    finally:
        # Cleanup failure cannot skip another owner or replace the original error.
        original_error = sys.exc_info()[1]
        cleanup_errors = await cleanup_owned(hass, fixture, base, child, drain)
        if child is not None:
            child_code = child.returncode
        if cleanup_errors and failure is None:
            failure = f"{type(cleanup_errors[0]).__name__}: {cleanup_errors[0]}"
        try:
            imports = {}
            for name, module in list(sys.modules.items()):
                path = getattr(module, "__file__", None)
                if path and (
                    name.startswith("custom_components.uninus_nutriculture")
                    or name in ("conftest", "p2_fixtures", "p3_fixtures")
                    or name.startswith("test_p")
                ):
                    source = Path(path).resolve()
                    assert source.is_relative_to(ROOT), (name, source)
                    imports[name] = {
                        "path": str(source),
                        "sha256": digest(source.read_bytes()),
                    }
            write(run / "actual-imports.json", imports)
            after_sources = inventory()
            write(run / "source-after.json", after_sources)
            write(run / "source-guard.json", {"unchanged": before_sources == after_sources})
            result = {
                "exit_code": 1 if failure else 0,
                "browser_exit_code": child_code,
                "failure": failure,
                "events": events,
                "native_requests": len(wire),
                "source_unchanged": before_sources == after_sources,
                "smoke_only": smoke_only,
                "child_pid": child.pid if child else None,
            }
            write(run / "result.json", result)
            write(
                out / "CHECKPOINT.json",
                {"state": "finished", "attempt": str(run), **result},
            )
            print(json.dumps(result), flush=True)
            assert before_sources == after_sources, "readonly source guard failed"
        except BaseException:
            if original_error is None and not cleanup_errors:
                raise
            traceback.print_exc(file=sys.stderr)
        if original_error is None and cleanup_errors:
            raise cleanup_errors[0]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--readback":
        asyncio.run(readback(Path(sys.argv[2]), sys.argv[3]))
    else:
        asyncio.run(main())
