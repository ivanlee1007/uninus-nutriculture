"""Isolated real Core 2026.10.4 Recorder -> registered History -> shipping Card.

SDK Python -B tools/p5b_history_native.py --out ABSENT_ATTEMPT --card-python EXE
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
    from conftest import entry, make_hass
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
        hass = await make_hass(out / "private-ha")
        if args.fault == "after-core":
            raise RuntimeError("injected after-core")
        from homeassistant.helpers.recorder import async_initialize_recorder

        async_initialize_recorder(hass)
        assert await async_setup_component(
            hass,
            "recorder",
            {
                "recorder": {
                    "db_url": "sqlite:///" + str(out / "private-ha/history.db").replace("\\", "/"),
                    "auto_purge": False,
                    "commit_interval": 1,
                    "include": {"domains": ["sensor"]},
                }
            },
        )
        recorder = get_instance(hass)
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
        entries = []
        for index in range(2):
            e = entry("Same tank")
            if index:
                from homeassistant.config_entries import ConfigEntry

                e = ConfigEntry(
                    domain=e.domain,
                    title=e.title,
                    data={**e.data, **{k: "sensor.history_b_" + k for k in ("ph", "ec", "level")}},
                    options={},
                    source="user",
                    version=1,
                    minor_version=1,
                    unique_id=None,
                    discovery_keys={},
                    subentries_data=[],
                )
            await hass.config_entries.async_add(e)
            await hass.async_block_till_done()
            entries.append(e)
        assert len({e.entry_id for e in entries}) == 2
        status_ids = [target(hass, e, "sensor", "control_status") for e in entries]
        mappings = [dict(hass.states.get(s).attributes["source_entities"]) for s in status_ids]
        assert all(set(m) == {"ph", "ec", "level"} and len(set(m.values())) == 3 for m in mappings)
        assert not set(mappings[0].values()) & set(mappings[1].values())
        users = {"all": admin}
        for name, allowed in [("partial", [mappings[0]["ph"]]), ("none", [])]:
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
        for step in range(3):
            for index, mapping in enumerate(mappings):
                for metric, source in mapping.items():
                    unit = {"ph": "pH", "ec": "mS/cm", "level": "m"}[metric]
                    value = {
                        "ph": 6.15 + index + step * 0.1,
                        "ec": 0.85 + index + step * 0.1,
                        "level": 1.25 + index + step * 0.1,
                    }[metric]
                    state = "unknown" if step == 1 else format(value, ".2f")
                    hass.states.async_set(
                        source,
                        state,
                        {"unit_of_measurement": unit, "history_sample": step},
                        force_update=True,
                    )
                    s = hass.states.get(source)
                    seeded.append(
                        {
                            "source": source,
                            "state": s.state,
                            "attributes": dict(s.attributes),
                            "last_updated": s.last_updated.isoformat(),
                        }
                    )
            await hass.async_block_till_done()
            await asyncio.wait_for(recorder.async_block_till_done(), 15)
            await asyncio.sleep(0.03)
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
                    "commissioning": "uncommissioned fixture; no physical outputs owned; NOT two full commissioned flows",
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
            allowed = {"get_quality_v1", "get_plan_v5", "get_flow_plan_v5"}
            unexpected = [c for c in service_calls if c.get("service") not in allowed]
            assert not unexpected, unexpected
            result = {
                "options_unchanged": True,
                "options_commits": len(mutations),
                "service_calls": service_calls,
                "feature_mutations": 0,
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
                    assert set(r["result"]) == {mappings[0]["ph"]}
                for source, rows in r["result"].items():
                    assert len(rows) == 3, (source, rows)
                    assert [r["s"] for r in rows][1] == "unknown"
                    assert all(
                        set(r) <= {"s", "a", "lu", "lc"}
                        and isinstance(r["lu"], (int, float))
                        and r["lu"] > 1e9
                        and isinstance(r["a"], dict)
                        for r in rows
                    ), rows
                    expected = [s for s in seeded if s["source"] == source]
                    assert [r["s"] for r in rows] == [s["state"] for s in expected]
                    assert [r["a"] for r in rows] == [s["attributes"] for s in expected]
                proof.append(
                    {
                        "hours": hours,
                        "principal": principal,
                        "sources": list(r["result"]),
                        "request_id": r["id"],
                    }
                )
        other_msg = {**msg, "entity_ids": list(mappings[1].values())}
        other_reply = (await native(other_msg, admin.id))["reply"]
        assert other_reply["success"] and set(other_reply["result"]) == set(mappings[1].values())
        for metric, source in mappings[1].items():
            expected = [s for s in seeded if s["source"] == source]
            assert [r["s"] for r in other_reply["result"][source]] == [s["state"] for s in expected]
        proof.append(
            {
                "hours": 24,
                "principal": "all",
                "entry_index": 1,
                "sources": list(other_reply["result"]),
                "request_id": other_reply["id"],
            }
        )
        assert (
            hashlib.sha256(Path(history_ws.__file__).read_bytes()).hexdigest()
            == "5b3fdf3acfa0c8e254819473e24408a9d54d3b0cedb8cda6f13551b5bf8ed7c0"
        )
        with sqlite3.connect(out / "private-ha/history.db") as db:
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
                    "both entries uncommissioned; no two-flow or shared-output acceptance",
                    "ActiveConnection auth principal is AuthManager user; no HTTP bearer handshake exercised",
                ],
            },
        )
        write(
            out / "CHECKPOINT.json",
            {"state": "wire_certified", "requests": len(wire), "desired_ui": "pending"},
        )
        if args.fault == "after-wire":
            raise RuntimeError("injected after-wire")
        if not args.wire_only:
            env = dict(os.environ, P5B_CARD_BUNDLE=str(card / "uninus-nutriculture-card.js"))
            command = [args.card_python, "-B", str(card / "tests/p5b_history_native_browser.py")]
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
                raise AssertionError("shipping desired-history UI failed; see browser.stderr.log")
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
        stopped = hass is not None and hass.state is CoreState.stopped
        recorder_alive = recorder.is_alive() if recorder else False
        if not stopped or recorder_alive or any(not r["ok"] for r in cleanup):
            failure = failure or "cleanup lifecycle failed"
        imports = {}
        for name, module in list(sys.modules.items()):
            origin = getattr(module, "__file__", None)
            if origin and (
                name.startswith("custom_components.uninus_nutriculture")
                or name in ("conftest", "test_p2_control")
            ):
                source = Path(origin).resolve()
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                canonical = backend.joinpath(*name.split(".")).with_suffix(".py")
                if not canonical.is_file():
                    canonical = backend.joinpath(*name.split(".")) / "__init__.py"
                if name in ("conftest", "test_p2_control"):
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
