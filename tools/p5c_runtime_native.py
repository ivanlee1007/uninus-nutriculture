"""Isolated real Core 2026.10.4 Recorder -> registered History -> shipping Card.

SDK Python -B tools/p5c_runtime_native.py --out ABSENT_ATTEMPT --card-python EXE
Optional --source-pair PAIR --wire-only --fault after-wire|after-core|after-child
Runtime/auth/captures stay private under explicit OUT. No production substitutions.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata as metadata
import json
import logging
import os
import sqlite3
import sys
import traceback
from datetime import timedelta
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import homeassistant  # noqa: F401 -- establish schema compatibility before fixture imports
from homeassistant.helpers.json import json_bytes


def serial(v):
    return json.loads(json_bytes(v))


def write(path, v):
    path.write_text(json.dumps(serial(v), ensure_ascii=False, indent=2), encoding="utf-8")


def inventory(pair):
    return {
        p.relative_to(pair).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for name in ("uninus-nutriculture", "uninus-nutriculture-card")
        for p in (pair / name).rglob("*")
        if p.is_file()
    }


async def main(args):
    pair = (
        Path(args.source_pair).resolve()
        if args.source_pair
        else Path(__file__).resolve().parents[2]
    )
    backend = pair / "uninus-nutriculture"
    card = pair / "uninus-nutriculture-card"
    out = Path(args.out).resolve()
    assert not out.is_relative_to(pair) and not pair.is_relative_to(out)
    out.mkdir(parents=True, exist_ok=False)
    os.chdir(out)
    for key in ("P3C_CAPTURE_DIR", "P3C_TERMINAL_ROOT", "P4B_JOIN_OUTPUT", "P5A_JOIN_OUTPUT"):
        assert not os.environ.get(key), f"unexpected legacy writer {key}"
    sys.path[:0] = [str(backend), str(backend / "tests")]
    from homeassistant.auth import auth_manager_from_config
    from homeassistant.auth.const import GROUP_ID_ADMIN
    from homeassistant.auth.models import Group
    from homeassistant.auth.permissions.const import POLICY_READ
    from homeassistant.components.history import websocket_api as history_ws
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.websocket_api.connection import ActiveConnection
    from homeassistant.core import CoreState
    from homeassistant.helpers import device_registry as dr
    from homeassistant.setup import async_setup_component
    from homeassistant.util import dt as dt_util
    from test_p2_control import target

    versions = {
        k: metadata.version(k)
        for k in ("homeassistant", "SQLAlchemy", "fnv-hash-fast", "psutil-home-assistant", "psutil")
    }
    assert versions["homeassistant"] == "2026.10.4", versions
    assert (
        versions["SQLAlchemy"] == "2.0.54"
        and versions["fnv-hash-fast"] == "2.0.3"
        and versions["psutil-home-assistant"] == "0.0.1"
    ), versions
    before = inventory(pair)
    write(out / "source-before.json", before)
    for relative in before:
        dst = out / "source-bytes" / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((pair / relative).read_bytes())
    write(
        out / "command.json",
        {
            "argv": sys.argv,
            "python": sys.executable,
            "versions": versions,
            "source_pair": str(pair),
            "env": {
                k: os.environ.get(k)
                for k in ("NODE", "CHROMIUM_EXECUTABLE", "PYTHONDONTWRITEBYTECODE")
            },
        },
    )
    write(
        out / "CHECKPOINT.json",
        {"state": "starting", "native_wire": "pending", "browser": "pending"},
    )
    hass = None
    base_fixture = None
    dosing_fixture = None
    child = None
    stderr_task = None
    recorder = None
    failure = None
    child_code = None
    wire = []
    events = []
    cleanup = []
    connections = []
    service_calls = []
    mutations = []
    options_before = None
    try:
        import p2_fixtures
        from p2_fixtures import control_hass
        from test_p2_control import toggle
        from test_p3_dosing import dosing_hass, start_native
        from test_p3c_flow import prepared, save_v5, until

        # Compose ONLY the owned test fixture's Core factory so Recorder registers
        # before SwitchEntity installs entity-registry listeners. No SDK substitution.
        original_factory = p2_fixtures.make_hass

        async def recorded_core(directory):
            nonlocal hass, recorder
            hass = await original_factory(directory)
            if args.fault == "after-core":
                raise RuntimeError("injected after-core")
            from homeassistant.helpers.recorder import async_initialize_recorder

            async_initialize_recorder(hass)
            assert await async_setup_component(
                hass,
                "recorder",
                {
                    "recorder": {
                        "db_url": "sqlite:///"
                        + str(out / "private-ha/control-ha/history.db").replace("\\", "/"),
                        "auto_purge": False,
                        "commit_interval": 1,
                        "include": {"domains": ["sensor"]},
                    }
                },
            )
            recorder = get_instance(hass)
            return hass

        p2_fixtures.make_hass = recorded_core
        try:
            base_fixture = control_hass.__wrapped__(out / "private-ha")
            await anext(base_fixture)
        finally:
            p2_fixtures.make_hass = original_factory
        dosing_fixture = dosing_hass.__wrapped__(hass)
        await anext(dosing_fixture)
        # Real component registration, no hand-written handler or schema.
        history_ws.async_setup(hass)
        dr.async_get(hass)
        from homeassistant.components.websocket_api import async_register_command, commands

        async_register_command(hass, commands.handle_call_service)
        hass.auth = await auth_manager_from_config(hass, [], [])
        await hass.auth.async_create_user("Owned fixture owner")
        admin = await hass.auth.async_create_user("Owned admin", group_ids=[GROUP_ID_ADMIN])
        assert admin.is_admin and not admin.is_owner
        # Provision real AuthStore groups; real PolicyPermissions and filter run unmodified.
        # Canonical Options + registered v5 writer on existing fake SwitchEntities.
        # These are native projected states, NOT manually written status/quality/result DTOs.
        e, acid = await prepared(hass)
        flow_plan = {
            "rows": [
                dict(
                    stage=stage,
                    start_rule="flow_start" if i == 0 else "after_previous_finished",
                    delay_seconds=0,
                    condition=None,
                    wait_timeout_seconds=20,
                )
                for i, stage in enumerate(("nutrient", "refill", "acid", "mix"))
            ],
            "run_timeout_seconds": 120,
        }
        await save_v5(hass, e, flow_plan)
        # Synthetic input above the native safe dosing level; no status DTO writes.
        hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
        await toggle(hass, e, "automation_enabled")
        await toggle(hass, e, "nutrient_enabled")
        entries = [e]
        status_ids = [target(hass, e, "sensor", "control_status")]
        quality_ids = [target(hass, e, "sensor", "quality_status")]
        result_ids = [target(hass, e, "sensor", "result_status")]
        mappings = [dict(status=status_ids[0], quality=quality_ids[0], result=result_ids[0])]
        assert hass.states.get(status_ids[0]).attributes["schema_version"] == 5
        users = {"all": admin}
        for name, allowed in [("partial", [status_ids[0]]), ("none", [])]:
            group = Group(
                name=name, policy={"entities": {"entity_ids": {s: {"read": True} for s in allowed}}}
            )
            hass.auth._store._groups[group.id] = group
            users[name] = await hass.auth.async_create_user("Owned " + name, group_ids=[group.id])
            for source in mappings[0].values():
                assert users[name].permissions.check_entity(source, POLICY_READ) == (
                    source in allowed
                )
        await hass.async_start()
        await asyncio.wait_for(recorder.async_recorder_ready.wait(), 15)
        seeded = []

        async def capture(label):
            # StateMachine/Recorder barriers, never fake SQL or historical API replies.
            for _ in range(20):
                await asyncio.sleep(0)
            for source in mappings[0].values():
                state = hass.states.get(source)
                seeded.append(
                    {
                        "label": label,
                        "source": source,
                        "state": state.state,
                        "attributes": serial(dict(state.attributes)),
                        "last_updated": state.last_updated.isoformat(),
                    }
                )
            write(out / "seeded-native-states.json", seeded)
            await asyncio.wait_for(recorder.async_block_till_done(), 15)

        await capture("native_v5_idle")
        accepted = await start_native(hass, e)
        assert accepted["accepted"], accepted
        pump, circulation = hass.data["p3_fixture"]["outputs"]
        await asyncio.wait_for(pump.entered_on.wait(), 3)
        await until(
            lambda: hass.states.get(status_ids[0]).attributes["output_states"]["nutrient"] == "on"
        )
        await capture("native_fakehardware_nutrient_on")
        await toggle(hass, e, "flow_run", False)
        await until(lambda: not e.runtime_data.control.running)
        assert not pump.is_on and not circulation.is_on and not acid.is_on
        await capture("native_operator_stopped_outputs_off")
        assert any(
            x["attributes"].get("output_states", {}).get("nutrient") == "on" for x in seeded
        ), seeded
        hardware_before = serial(
            {"refill": hass.data["p2_fixture"]["calls"], "dosing": hass.data["p3_fixture"]["calls"]}
        )
        write(out / "setup-fakehardware-calls.json", hardware_before)
        options_before = serial([dict(e.options) for e in entries])

        def observe(event):
            service_calls.append(serial(dict(event.data)))

        hass.bus.async_listen("call_service", observe)
        for e in entries:
            e.add_update_listener(lambda _h, _e: mutations.append("options_update"))
        write(out / "seeded-native-states.json", seeded)
        qualification = []
        for e, s, m in zip(entries, status_ids, mappings):
            qualification.append(
                {
                    "entry_id": e.entry_id,
                    "title": e.title,
                    "state": e.state.value,
                    "status_id": s,
                    "status": serial(hass.states.get(s).as_dict()),
                    "source_entities": m,
                    "commissioning": "one native S5 stopped nutrient run; existing isolated fake SwitchEntities only; no physical equipment or commissioned multislots",
                    "quality_id": quality_ids[0],
                    "result_id": result_ids[0],
                }
            )
        write(out / "entries.json", qualification)
        pending = {}
        transport_id = 0

        def connection(user):
            def send(message):
                raw = (
                    message
                    if isinstance(message, bytes)
                    else message.encode()
                    if isinstance(message, str)
                    else json_bytes(message)
                )
                reply = json.loads(raw)
                (out / f"wire-{reply['id']:04d}.raw.json").write_bytes(raw)
                future = pending.get(reply.get("id"))
                if future is not None and not future.done():
                    future.set_result(reply)

            c = ActiveConnection(logging.getLogger("owned.history"), hass, send, user, None, None)
            connections.append(c)
            return c

        by_user = {u.id: connection(u) for u in users.values()}

        async def native(message, user_id):
            nonlocal transport_id
            user = await hass.auth.async_get_user(user_id)
            assert user and user.is_active and user.id in by_user
            transport_id += 1
            request = {**message, "id": transport_id}
            assert {k: v for k, v in request.items() if k != "id"} == message
            pending[transport_id] = asyncio.get_running_loop().create_future()
            by_user[user_id].async_handle(request)
            reply = await asyncio.wait_for(pending[transport_id], 20)
            wire.append(
                {"emitted": message, "request": request, "principal_id": user_id, "reply": reply}
            )
            write(out / "wire.json", wire)
            return {"reply": reply}

        def snapshot(index=0, principal="all"):
            u = users[principal]
            return {
                "status_id": status_ids[index],
                "quality_id": quality_ids[index],
                "result_id": result_ids[index],
                "user_id": u.id,
                "is_admin": u.is_admin,
                "states": {s.entity_id: serial(s.as_dict()) for s in hass.states.async_all()},
                "services": {
                    d: {s: {} for s in svcs} for d, svcs in hass.services.async_services().items()
                },
            }

        async def inspect():
            assert serial([dict(e.options) for e in entries]) == options_before
            assert not mutations, mutations
            assert (
                serial(
                    {
                        "refill": hass.data["p2_fixture"]["calls"],
                        "dosing": hass.data["p3_fixture"]["calls"],
                    }
                )
                == hardware_before
            )
            assert not entries[0].runtime_data.control.running
            allowed = {"get_quality_v1", "get_plan_v5", "get_flow_plan_v5"}
            unexpected = [c for c in service_calls if c.get("service") not in allowed]
            assert not unexpected, unexpected
            result = {
                "options_unchanged": True,
                "options_commits": len(mutations),
                "service_calls": service_calls,
                "feature_mutations": 0,
                "browser_actuator_calls": 0,
            }
            write(out / "zero-mutations.json", result)
            return result

        # Bootstrap and wire are independently certified BEFORE desired UI assertions.
        proof = []
        now = dt_util.utcnow()
        for hours in (1, 6, 24):
            msg = {
                "type": "history/history_during_period",
                "entity_ids": list(mappings[0].values()),
                "start_time": (now - timedelta(hours=hours)).isoformat(),
                "end_time": now.isoformat(),
                "include_start_time_state": True,
                "significant_changes_only": False,
                "minimal_response": False,
                "no_attributes": False,
            }
            for principal, count in [("all", 3), ("partial", 1), ("none", 0)]:
                r = (await native(msg, users[principal].id))["reply"]
                assert r["success"], r
                assert len(r["result"]) == count, r
                if principal == "partial":
                    assert set(r["result"]) == {status_ids[0]}
                for source, rows in r["result"].items():
                    assert rows and all(
                        set(row) <= {"s", "a", "lu", "lc"}
                        and isinstance(row["lu"], (int, float))
                        and row["lu"] > 1e9
                        and isinstance(row["a"], dict)
                        for row in rows
                    ), rows
                    for expected in (sample for sample in seeded if sample["source"] == source):
                        assert any(
                            row["s"] == expected["state"] and row["a"] == expected["attributes"]
                            for row in rows
                        ), (expected, rows)
                if principal == "all":
                    status_rows = [
                        row
                        for row in r["result"][status_ids[0]]
                        if row["a"].get("schema_version") == 5
                    ]
                    assert any(row["a"]["output_states"]["nutrient"] == "on" for row in status_rows)
                    assert any(
                        row["a"]["output_states"]["nutrient"] == "off" for row in status_rows
                    )
                    assert any(
                        row["a"].get("last_result") is not None
                        for row in r["result"][result_ids[0]]
                    )
                proof.append(
                    {
                        "hours": hours,
                        "principal": principal,
                        "sources": list(r["result"]),
                        "request_id": r["id"],
                    }
                )
        missing_id = "sensor.p5c_never_recorded_optional"
        missing_reply = (await native({**msg, "entity_ids": [missing_id]}, admin.id))["reply"]
        assert missing_reply["success"] and missing_reply["result"] == {}, missing_reply
        proof.append(
            {
                "principal": "all",
                "missing_entity": missing_id,
                "request_id": missing_reply["id"],
                "result": {},
            }
        )
        assert (
            hashlib.sha256(Path(history_ws.__file__).read_bytes()).hexdigest()
            == "5b3fdf3acfa0c8e254819473e24408a9d54d3b0cedb8cda6f13551b5bf8ed7c0"
        )
        with sqlite3.connect(out / "private-ha/control-ha/history.db") as db:
            counts = db.execute(
                "SELECT m.entity_id,count(*) FROM states s JOIN states_meta m ON s.metadata_id=m.metadata_id GROUP BY m.entity_id"
            ).fetchall()
        assert all(dict(counts).get(s, 0) >= 3 for m in mappings for s in m.values()), counts
        write(
            out / "wire-proof.json",
            {
                "core": versions["homeassistant"],
                "recorder": "native SQLite states/events; no SQL writes",
                "sqlite_readback_counts": counts,
                "registered_handler_file": history_ws.__file__,
                "registered_handler_sha256": hashlib.sha256(
                    Path(history_ws.__file__).read_bytes()
                ).hexdigest(),
                "proof": proof,
                "flags": {
                    k: msg[k]
                    for k in (
                        "include_start_time_state",
                        "significant_changes_only",
                        "minimal_response",
                        "no_attributes",
                    )
                },
                "limitations": [
                    "samples are real recent events, not a simulated 24h retention span",
                    "one canonical S5 nutrient run/stopped using existing fake SwitchEntities; no physical equipment",
                    "sensor inputs are synthetic; status, quality and result are integration-produced StateMachine events",
                    "no granted permit or successful four-stage completion claimed; quality/result use actual native DTOs",
                    "ActiveConnection auth principal is AuthManager user; no HTTP bearer handshake exercised",
                ],
            },
        )
        write(
            out / "CHECKPOINT.json",
            {
                "state": "SETUP_READY",
                "requests": len(wire),
                "desired_ui": "pending",
                "recorded": "native S5 nutrient ON then operator stop/OFF; real optional quality/result",
            },
        )
        if args.fault == "after-wire":
            raise RuntimeError("injected after-wire")
        if args.wire_only:
            events.append({"kind": "checkpoint", "case": "SETUP_READY_not_UI_acceptance"})
        if not args.wire_only:
            env = dict(os.environ, P5C_CARD_BUNDLE=str(card / "uninus-nutriculture-card.js"))
            command = [args.card_python, "-B", str(card / "tests/p5c_runtime_native_browser.py")]
            child = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=8 * 1024 * 1024,
                env=env,
                cwd=out,
            )
            write(out / "child.json", {"pid": child.pid, "command": command})

            async def drain_stderr():
                with (out / "browser.stderr.log").open("wb") as f:
                    while chunk := await child.stderr.read(65536):
                        f.write(chunk)

            stderr_task = asyncio.create_task(drain_stderr())
            if args.fault == "after-child":
                raise RuntimeError("injected after-child")
            async with asyncio.timeout(240):
                while line := await asyncio.wait_for(child.stdout.readline(), 35):
                    with (out / "ipc.raw.jsonl").open("ab") as f:
                        f.write(line)
                    m = json.loads(line)
                    kind = m["kind"]
                    payload = m.get("payload") or {}
                    try:
                        if kind == "snapshot":
                            result = snapshot(**payload)
                        elif kind == "ws":
                            result = await native(payload["message"], payload["principal_id"])
                        elif kind == "inspect":
                            result = await inspect()
                        elif kind in ("checkpoint", "done"):
                            events.append({"kind": kind, **payload})
                            result = {}
                            write(out / "events.json", events)
                        else:
                            raise ValueError(kind)
                    except Exception as e:
                        failure = "harness_error: " + repr(e)
                        result = {"harness_error": failure}
                        traceback.print_exc(file=sys.stderr)
                    raw = json_bytes(result) + b"\n"
                    with (out / "ipc-replies.raw.jsonl").open("ab") as f:
                        f.write(raw)
                    child.stdin.write(raw)
                    await child.stdin.drain()
                child_code = await asyncio.wait_for(child.wait(), 10)
                await asyncio.wait_for(stderr_task, 10)
            if child_code:
                raise AssertionError(
                    "shipping desired-runtime/trace UI failed; see browser.stderr.log"
                )
            assert events and events[-1]["kind"] == "done"
        await inspect()
    except BaseException as e:
        failure = failure or f"{type(e).__name__}: {e}"
        traceback.print_exc(file=sys.stderr)
    finally:

        async def attempt(name, fn):
            try:
                await asyncio.wait_for(fn(), 20)
                cleanup.append({"owner": name, "ok": True})
            except BaseException as e:
                cleanup.append({"owner": name, "ok": False, "error": repr(e)})
                traceback.print_exc(file=sys.stderr)

        # Assert read-only effects even when desired UI assertions or injected faults fail.
        if options_before is not None:
            await attempt("read_only_effects", inspect)
        if hass is not None:
            await attempt("core.async_stop", lambda: hass.async_stop(force=True))
        if child is not None:

            async def close_child():
                if child.stdin:
                    child.stdin.close()
                if child.returncode is None:
                    child.kill()
                await child.wait()

            await attempt("child.wait", close_child)
            await attempt("child.stdout.drain", child.stdout.read)
            if stderr_task is not None:
                await attempt("child.stderr.drain", lambda: stderr_task)
            child_code = child.returncode
        if dosing_fixture is not None:
            await attempt("dosing_fixture.aclose", dosing_fixture.aclose)
        if base_fixture is not None:
            await attempt("base_fixture.aclose", base_fixture.aclose)
        stopped = hass is not None and hass.state is CoreState.stopped
        recorder_alive = recorder.is_alive() if recorder else False
        if not stopped or recorder_alive or any(not r["ok"] for r in cleanup):
            failure = failure or "cleanup lifecycle failed"
        imports = {}
        for name, module in list(sys.modules.items()):
            origin = getattr(module, "__file__", None)
            if origin and (
                name.startswith("custom_components.uninus_nutriculture")
                or name
                in (
                    "conftest",
                    "p2_fixtures",
                    "test_p2_control",
                    "test_p3_dosing",
                    "test_p3c_flow",
                    "p3_fixtures",
                )
            ):
                source = Path(origin).resolve()
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                canonical = backend.joinpath(*name.split(".")).with_suffix(".py")
                if not canonical.is_file():
                    canonical = backend.joinpath(*name.split(".")) / "__init__.py"
                if name in (
                    "conftest",
                    "p2_fixtures",
                    "test_p2_control",
                    "test_p3_dosing",
                    "test_p3c_flow",
                    "p3_fixtures",
                ):
                    canonical = backend / "tests" / f"{name}.py"
                matches = (
                    canonical.is_file()
                    and hashlib.sha256(canonical.read_bytes()).hexdigest() == digest
                )
                imports[name] = {
                    "path": str(source),
                    "sha256": digest,
                    "canonical_path": str(canonical),
                    "canonical_bytes_equal": matches,
                }
                if not matches:
                    failure = failure or "import provenance mismatch: " + name
        write(out / "actual-imports.json", imports)
        after = inventory(pair)
        write(out / "source-after.json", after)
        unchanged = before == after
        if not unchanged:
            failure = failure or "source tree changed"
        result = {
            "exit_code": 1 if failure else 0,
            "failure": failure,
            "browser_exit_code": child_code,
            "wire_requests": len(wire),
            "events": events,
            "core_state": str(hass.state) if hass else None,
            "core_STOPPED": stopped,
            "recorder_thread_alive": recorder_alive,
            "cleanup": cleanup,
            "source_unchanged": unchanged,
            "fault": args.fault,
            "wire_only": args.wire_only,
            "verdict": "FAILED"
            if failure
            else "SETUP_READY"
            if args.wire_only
            else "NATIVE_UI_ACCEPTED",
        }
        write(out / "result.json", result)
        write(out / "CHECKPOINT.json", {"state": "finished", **result})
        print(json.dumps(result), flush=True)
    return 1 if failure else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--source-pair")
    p.add_argument("--card-python", required=True)
    p.add_argument("--wire-only", action="store_true")
    p.add_argument("--fault", choices=("after-wire", "after-core", "after-child"))
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    sys.exit(asyncio.run(main(p.parse_args())))
