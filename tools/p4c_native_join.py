# ruff: noqa: E402
# Native source routing and HA initialization must precede fixture imports.
import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import traceback
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Portable P4c real native Core/shipped Card acceptance"
)
parser.add_argument("--output", default=os.environ.get("P4C_JOIN_OUTPUT"))
parser.add_argument("--card-repo", default=os.environ.get("P4C_CARD_REPO"))
parser.add_argument("--smoke", action="store_true")
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
F = ROOT.parent
CARD = Path(args.card_repo).resolve() if args.card_repo else F / "uninus-nutriculture-card"
assert (CARD / "uninus-nutriculture-card.js").is_file()
if args.smoke:
    print(
        json.dumps(
            {
                "backend": str(ROOT),
                "card": str(CARD),
                "fixtures": (ROOT / "tests/p2_fixtures.py").is_file(),
            }
        )
    )
    sys.exit(0)
if not args.output:
    parser.error("--output or P4C_JOIN_OUTPUT required")
OUT = Path(args.output).resolve()
assert not OUT.is_relative_to(ROOT) and not OUT.is_relative_to(CARD)
OUT.mkdir(parents=True, exist_ok=False)
os.environ.update(
    P4C_SOURCE=str(F), P4C_RUN=str(OUT), P4C_CARD_REPO=str(CARD), PYTHONDONTWRITEBYTECODE="1"
)
os.environ.setdefault("P4C_CARD_PYTHON", sys.executable)
import homeassistant
from p4c_source_inputs import source_hashes

source_before = source_hashes(ROOT, CARD)
(OUT / "source-before.json").write_text(json.dumps(source_before, indent=2), encoding="utf-8")
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.chdir(OUT)
from homeassistant.auth import auth_manager_from_config
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.websocket_api import async_register_command, commands
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import Context, callback
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.storage import Store
from p2_fixtures import control_hass
from p4c_four_stage import drive
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass, start_native
from test_p3_stage_projection import snapshot
from test_p3c_flow import STAGES, prepared, save_v5, until

logging.basicConfig(level=logging.WARNING)


def serial(v):
    return json.loads(json_bytes(v))


def write(n, v):
    (OUT / n).write_text(json.dumps(serial(v), ensure_ascii=False, indent=2), encoding="utf-8")


wire = []
checkpoints = []
child = None


async def main():
    global child
    base = control_hass.__wrapped__(OUT)
    h = await anext(base)
    fixture = dosing_hass.__wrapped__(h)
    await anext(fixture)
    drain = None
    code = None
    try:
        e, acid = await prepared(h)
        await save_v5(h, e)
        await h.async_block_till_done()
        h.auth = await auth_manager_from_config(h, [], [])
        await h.auth.async_create_user("Owned fixture owner")
        user = await h.auth.async_create_user("Owned nonowner admin", group_ids=[GROUP_ID_ADMIN])
        assert user.is_admin and not user.is_owner
        async_register_command(h, commands.handle_call_service)
        future = None

        def send(msg):
            nonlocal future
            if isinstance(msg, (str, bytes)):
                msg = json.loads(msg)
            if future is not None and not future.done():
                future.set_result(serial(msg))

        conn = ActiveConnection(
            logging.getLogger("owned.native.connection"), h, send, user, None, None
        )

        def snap():
            return serial(
                {
                    **snapshot(h, e),
                    "result_id": target(h, e, "sensor", "result_status"),
                    "user_id": user.id,
                    "services": {
                        d: {k: {} for k in v} for d, v in h.services.async_services().items()
                    },
                }
            )

        def io():
            return serial(
                {
                    "refill": h.data["p2_fixture"]["calls"],
                    "dosing": h.data["p3_fixture"]["calls"],
                    "acid_on": acid.is_on,
                }
            )

        async def native_ws(payload):
            nonlocal future
            future = asyncio.get_running_loop().create_future()
            req = {**payload, "id": conn.last_id + 1}
            conn.async_handle(req)
            reply = await asyncio.wait_for(future, 15)
            await h.async_block_till_done()
            wire.append({"request": req, "reply": reply, "io": io()})
            write("wire.json", wire)
            return {"reply": reply, "snapshot": snap()}

        write(
            "registered-routes.json",
            sorted(k for k in h.data["websocket_api"] if "notification_v1" in k),
        )
        childcmd = [
            os.environ["P4C_CARD_PYTHON"],
            "-B",
            str(Path(__file__).with_name("p4c_browser_join.py")),
        ]
        write(
            "commands.json",
            {
                "parent": [sys.executable, "-B", str(Path(__file__).resolve())],
                "child": childcmd,
                "source": str(F),
                "cwd": str(OUT),
                "sdk_core": homeassistant.__file__,
            },
        )
        child = await asyncio.create_subprocess_exec(
            *childcmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=4 * 1024 * 1024,
            cwd=OUT,
        )

        async def stderr():
            with (OUT / "browser.stderr.log").open("wb") as log:
                while chunk := await child.stderr.read(65536):
                    log.write(chunk)

        drain = asyncio.create_task(stderr())
        while line := await asyncio.wait_for(child.stdout.readline(), 90):
            with (OUT / "ipc.raw.jsonl").open("ab") as log:
                log.write(line)
            msg = json.loads(line)
            kind = msg["kind"]
            payload = msg.get("payload")
            result = {}
            try:
                if kind == "snapshot":
                    result = {"snapshot": snap()}
                elif kind == "ws":
                    result = await native_ws(payload)
                elif kind == "checkpoint":
                    checkpoints.append(payload)
                    write("checkpoints.json", checkpoints)
                    if len(checkpoints) == 1:
                        write(
                            "CHECKPOINT.json",
                            {
                                "status": "FIRST_REAL_REGISTERED_WS",
                                "checkpoint": payload,
                                "wire_count": len(wire),
                            },
                        )
                elif kind == "verify_store":
                    path = Path(
                        h.config.path(
                            ".storage", "uninus_nutriculture.notification_v1." + e.entry_id
                        )
                    )
                    doc = json.loads(path.read_text())
                    fresh = Store(
                        h,
                        1,
                        "uninus_nutriculture.notification_v1." + e.entry_id,
                        private=True,
                        atomic_writes=True,
                    )
                    loaded = await fresh.async_load()
                    assert loaded == doc["data"]
                    assert loaded["revision"] == payload["revision"] == 1
                    assert loaded["policy"] == payload["policy"]
                    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
                    write(
                        "physical-store.json",
                        {
                            "document": doc,
                            "fresh_store_load": loaded,
                            "card_cached": payload,
                            "zero_actuator_calls": True,
                        },
                    )
                    result = {"verified": True}
                elif kind == "native_options":
                    before = serial(dict(e.options))
                    revision = e.runtime_data.notifications.revision

                    async def open_form():
                        f = await h.config_entries.options.async_init(
                            e.entry_id, context={"user_id": user.id}
                        )
                        assert "notification_management" in {
                            str(k) for k in f["data_schema"].schema
                        }
                        f = await h.config_entries.options.async_configure(
                            f["flow_id"],
                            {
                                **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
                                "notification_management": True,
                            },
                        )
                        assert f["step_id"] == "notifications"
                        return f

                    values = dict(
                        enabled=True,
                        provider="persistent_notification",
                        events=["start", "completed"],
                        cooldown_seconds=600,
                        action="save",
                    )
                    f = await open_form()
                    r = await h.config_entries.options.async_configure(f["flow_id"], values)
                    assert r["type"] == "abort"
                    assert e.runtime_data.notifications.revision == revision + 1
                    f = await open_form()
                    schema = str(f["data_schema"])
                    r = await h.config_entries.options.async_configure(
                        f["flow_id"], {**values, "cooldown_seconds": 800, "action": "cancel"}
                    )
                    assert r["type"] == "abort"
                    assert (
                        e.runtime_data.notifications.revision == revision + 1
                        and serial(dict(e.options)) == before
                    )
                    assert e.runtime_data.notifications.dto()["policy"]["cooldown_seconds"] == 600
                    write(
                        "native-options.json",
                        {
                            "submitted": values,
                            "reopened_schema": schema,
                            "cancel_revision_unchanged": True,
                            "options_unchanged": True,
                            "revision": revision + 1,
                        },
                    )
                elif kind == "drive":
                    from homeassistant.components import persistent_notification as pn

                    notices = []
                    events = []

                    @callback
                    def notice(kind, messages):
                        notices.extend(serial(list(messages.values())))

                    unsub = pn.async_register_callback(h, notice)

                    @callback
                    def event(ev):
                        events.append(serial(dict(ev.data)))

                    unsubevent = h.bus.async_listen("uninus_nutriculture_result_v1", event)
                    for key in ["automation_enabled"] + [s + "_enabled" for s in STAGES]:
                        await toggle(h, e, key)
                    c = e.runtime_data.control
                    clock = c.mix_stage.clock
                    c.mix_stage.clock = lambda: clock() * 600
                    for _ in range(5):
                        await asyncio.sleep(0)

                    async def start_checked(hass, entry):
                        accepted = await start_native(hass, entry)
                        write("admission.json", accepted)
                        assert accepted["accepted"] is True
                        d = await h.services.async_call(
                            "uninus_nutriculture",
                            "get_result_v1",
                            {"config_entry_id": e.entry_id},
                            blocking=True,
                            return_response=True,
                            context=Context(user_id=user.id),
                        )
                        write("accepted-result.json", d)
                        assert d["current_run"] is not None and d["last_result"] is None
                        return accepted

                    status = await drive(h, e, acid, snap, start_checked, until, snapshot, asyncio)
                    d = await h.services.async_call(
                        "uninus_nutriculture",
                        "get_result_v1",
                        {"config_entry_id": e.entry_id},
                        blocking=True,
                        return_response=True,
                        context=Context(user_id=user.id),
                    )
                    native = dict(h.states.get(target(h, e, "sensor", "result_status")).attributes)
                    native.pop("friendly_name", None)
                    assert native == d
                    assert (
                        d["current_run"] is None
                        and d["last_result"]["state"] == "completed"
                        and d["last_result"]["closure"] == "confirmed"
                    )
                    for _ in range(10):
                        assert (
                            await h.services.async_call(
                                "uninus_nutriculture",
                                "get_result_v1",
                                {"config_entry_id": e.entry_id},
                                blocking=True,
                                return_response=True,
                                context=Context(user_id=user.id),
                            )
                            == d
                        )
                    await h.async_block_till_done()
                    assert notices and any("已受理" in n["message"] for n in notices)
                    delivery = e.runtime_data.notifications.dto()
                    assert [r["status"] for r in delivery["deliveries"]] == [
                        "handoff_returned",
                        "handoff_returned",
                    ]
                    write(
                        "terminal-native.json",
                        {
                            "dto": d,
                            "native_attributes": native,
                            "status": status,
                            "events": events,
                            "notices": notices,
                            "notification": delivery,
                            "io": io(),
                            "leases": dict(c.leases),
                            "flow_pending": c.flow.pending,
                        },
                    )
                    unsub()
                    unsubevent()
                    result = {"snapshot": snap()}
                elif kind == "done":
                    checkpoints.append({"name": "browser_done", **payload})
                    write("checkpoints.json", checkpoints)
                else:
                    raise ValueError(kind)
            except Exception as exc:
                traceback.print_exc()
                result = {"harness_error": type(exc).__name__ + ": " + str(exc)}
                write(
                    "first-native-exception.json",
                    {
                        "kind": kind,
                        "exception": result["harness_error"],
                        "traceback": traceback.format_exc(),
                    },
                )
            child.stdin.write(json_bytes(result) + b"\n")
            await child.stdin.drain()
        code = await asyncio.wait_for(child.wait(), 15)
        await asyncio.wait_for(drain, 15)
        write(
            "result.json",
            {
                "status": "CURRENT_PARTIAL_NATIVE_JOIN PASSED"
                if code == 0
                else "CURRENT_PARTIAL_NATIVE_JOIN FAIL",
                "raw_child_exit": code,
                "native_requests": len(wire),
                "checkpoints": len(checkpoints),
            },
        )
        if code:
            raise RuntimeError("Browser child failed; retained first counterexample")
    finally:
        try:
            if child and child.returncode is None:
                child.kill()
                await asyncio.wait_for(child.wait(), 10)
            if child and child.stdout:
                await asyncio.wait_for(child.stdout.read(), 10)
            if drain:
                await asyncio.wait_for(drain, 10)
        finally:
            try:
                imports = {}
                for name, module in list(sys.modules.items()):
                    path = getattr(module, "__file__", None)
                    if path and (
                        name.startswith("custom_components.uninus_nutriculture")
                        or name.startswith("test_p")
                        or name in ("p2_fixtures", "p3_fixtures", "conftest")
                    ):
                        p = Path(path).resolve()
                        imports[name] = {
                            "path": str(p),
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        }
                        assert p.is_relative_to(F), str(p)
                write("actual-imports.json", imports)
                write("source-after.json", source_hashes(ROOT, CARD))
            finally:
                try:
                    await fixture.aclose()
                finally:
                    await base.aclose()


if __name__ == "__main__":
    asyncio.run(main())
