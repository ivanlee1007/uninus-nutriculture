# ruff: noqa: E402
import asyncio
import hashlib
import json
import logging
import os
import sys
import traceback
from pathlib import Path

import homeassistant  # noqa: F401

TOOLS = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT.parent / "uninus-nutriculture-card"
OUT = Path(os.environ["P4A_JOIN_OUTPUT"]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
# ROOT is the candidate backend, never the original checkout
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.chdir(OUT)
from homeassistant.auth import auth_manager_from_config
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.websocket_api import async_register_command, commands
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.helpers.json import json_bytes
from p2_fixtures import control_hass
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass
from test_p3_stage_projection import snapshot
from test_p3c_flow import STAGES, plan, prepared, save_v5, until

logging.basicConfig(level=logging.WARNING)


def serial(v):
    return json.loads(json_bytes(v))


def write(p, v):
    (OUT / p).write_text(json.dumps(serial(v), ensure_ascii=False, indent=2), encoding="utf-8")


async def main():
    attempt = sys.argv[1] if len(sys.argv) > 1 else "attempt1"
    run = OUT / attempt
    run.mkdir(exist_ok=False)
    for name in ("p4a_recipe_browser.py", "p4a_recipe_native.py", "p4a_recipe_readback.py"):
        (run / name).write_bytes((TOOLS / name).read_bytes())
    write(
        attempt + "/command.json",
        {
            "parent": [sys.executable, "-B", str(TOOLS / "p4a_recipe_native.py"), attempt],
            "child": [
                os.environ.get("P4A_CARD_PYTHON", sys.executable),
                "-B",
                str(TOOLS / "p4a_recipe_browser.py"),
            ],
            "cwd": str(OUT),
            "env": {
                k: os.environ.get(k)
                for k in ("P4A_CARD_PYTHON", "CHROMIUM_EXECUTABLE", "PYTHONDONTWRITEBYTECODE")
            },
        },
    )
    base = control_hass.__wrapped__(run)
    hass = await anext(base)
    fixture = dosing_hass.__wrapped__(hass)
    await anext(fixture)
    child = None
    events = []
    wire = []
    commits = []
    try:
        entry, acid = await prepared(hass)
        _v4 = dict(entry.options)
        await save_v5(hass, entry)
        await hass.async_block_till_done()
        assert entry.options["control_contract_version"] == 5
        hass.auth = await auth_manager_from_config(hass, [], [])
        await hass.auth.async_create_user("Owned fixture owner")
        user = await hass.auth.async_create_user(
            "Owned fixture nonowner admin", group_ids=[GROUP_ID_ADMIN]
        )
        assert not user.is_owner and user.is_admin
        async_register_command(hass, commands.handle_call_service)
        future = None

        def send(message):
            nonlocal future
            if isinstance(message, (bytes, str)):
                message = json.loads(message)
            if future and not future.done():
                future.set_result(serial(message))

        conn = ActiveConnection(
            logging.getLogger("owned.native.connection"), hass, send, user, None, None
        )

        async def observe(h, e):
            commits.append(serial(dict(e.options)))

        entry.add_update_listener(observe)

        def snap():
            return {
                **snapshot(hass, entry),
                "user_id": user.id,
                "services": {
                    d: {k: {} for k in v} for d, v in hass.services.async_services().items()
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

        child = await asyncio.create_subprocess_exec(
            os.environ.get("P4A_CARD_PYTHON", sys.executable),
            "-B",
            str(TOOLS / "p4a_recipe_browser.py"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=4 * 1024 * 1024,
            cwd=OUT,
        )

        async def stderr():
            with (run / "browser.stderr.log").open("wb") as log:
                retained = 0
                while chunk := await child.stderr.read(65536):
                    if retained < 16 * 1024 * 1024:
                        log.write(chunk[: 16 * 1024 * 1024 - retained])
                    retained += len(chunk)

        drain = asyncio.create_task(stderr())
        transport_id = 0
        while True:
            line = await asyncio.wait_for(child.stdout.readline(), 65)
            if not line:
                break
            (run / "ipc.raw.jsonl").open("ab").write(line)
            msg = json.loads(line)
            kind = msg["kind"]
            payload = msg.get("payload")
            result = {}
            try:
                if kind == "ws":
                    transport_id += 1
                    future = asyncio.get_running_loop().create_future()
                    request = {**payload["message"], "id": transport_id}
                    conn.async_handle(request)
                    reply = await asyncio.wait_for(future, 15)
                    await hass.async_block_till_done()
                    result = {"reply": reply, "snapshot": snap()}
                    wire.append(
                        {
                            "request": request,
                            "reply": reply,
                            "options": dict(entry.options),
                            "io": io(),
                            "commit_count": len(commits),
                            "numbers": {
                                k: float(hass.states.get(target(hass, entry, "number", k)).state)
                                for k in entry.runtime_data.parameters
                            },
                        }
                    )
                    write(attempt + "/wire.json", wire)
                elif kind == "multistage_prepare":
                    await save_v5(hass, entry, plan())
                    for key in ["automation_enabled"] + [s + "_enabled" for s in STAGES]:
                        await toggle(hass, entry, key)
                    c = entry.runtime_data.control
                    clock = c.mix_stage.clock
                    c.mix_stage.clock = lambda: clock() * 600
                    for _ in range(5):
                        await asyncio.sleep(0)
                    result = {"snapshot": snap()}
                elif kind == "multistage_drive":
                    c = entry.runtime_data.control
                    pump, circ = hass.data["p3_fixture"]["outputs"]
                    refill = hass.data["p2_fixture"]["hardware"]
                    await until(lambda: refill.is_on)
                    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
                    await asyncio.wait_for(circ.entered_on.wait(), 3)
                    assert refill.is_on and circ.is_on
                    overlap = snap()
                    await until(lambda: c.flow.records["mix"]["result"] == "completed")
                    assert refill.is_on and not circ.is_on
                    hass.states.async_set("sensor.level", "2.4", {"unit_of_measurement": "m"})
                    await asyncio.wait_for(pump.entered_on.wait(), 3)
                    hass.states.async_set("sensor.ec", ".86", {"unit_of_measurement": "mS/cm"})
                    await until(lambda: c.nutrient_stage.phase == "waiting_sample")
                    hass.states.async_set("sensor.ec", ".87", {"unit_of_measurement": "mS/cm"})
                    await asyncio.wait_for(acid.entered_on.wait(), 3)
                    hass.states.async_set("sensor.ph", "5.6", {"sample": 2})
                    await until(lambda: c.acid_stage.phase == "waiting_sample")
                    hass.states.async_set("sensor.ph", "5.6", {"sample": 3})
                    await until(lambda: not c.running)
                    for _ in range(10):
                        await asyncio.sleep(0)
                    status = snap()
                    attr = status["states"][status["status_id"]]["attributes"]
                    assert attr["flow_state"] == "completed" and all(
                        r["result"] == "completed" for r in attr["step_runtime"].values()
                    )
                    assert all(v == "off" for v in attr["output_states"].values())
                    result = {"snapshot": status, "overlap": overlap, "io": io()}
                    write(attempt + "/multistage.json", result)
                elif kind == "store_readback":
                    expected = serial(dict(entry.options))
                    numbers = {
                        k: float(hass.states.get(target(hass, entry, "number", k)).state)
                        for k in entry.runtime_data.parameters
                    }
                    config_dir = hass.config.config_dir
                    await hass.async_stop(force=True)
                    fresh = await asyncio.create_subprocess_exec(
                        sys.executable,
                        "-B",
                        str(TOOLS / "p4a_recipe_readback.py"),
                        config_dir,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=OUT,
                        limit=4 * 1024 * 1024,
                    )
                    try:
                        stdout, stderr = await asyncio.wait_for(fresh.communicate(), 45)
                    finally:
                        if fresh.returncode is None:
                            fresh.kill()
                            await asyncio.wait_for(fresh.wait(), 10)
                    (run / "fresh.stdout.log").write_bytes(stdout)
                    (run / "fresh.stderr.log").write_bytes(stderr)
                    assert fresh.returncode == 0
                    result = json.loads(stdout.decode().strip().splitlines()[-1])
                    assert result["options"] == expected
                    assert result["effective_parameters"] == numbers
                    write(attempt + "/stop-fresh-process-readback.json", result)
                elif kind == "snapshot":
                    result = {"snapshot": snap()}
                elif kind == "inspect":
                    result = {
                        "options": dict(entry.options),
                        "io": io(),
                        "commit_count": len(commits),
                        "numbers": {
                            k: float(hass.states.get(target(hass, entry, "number", k)).state)
                            for k in entry.runtime_data.parameters
                        },
                        "snapshot": snap(),
                    }
                elif kind == "number_change":
                    await hass.services.async_call(
                        "number",
                        "set_value",
                        {
                            "entity_id": target(hass, entry, "number", "mix_duration"),
                            "value": payload,
                        },
                        blocking=True,
                    )
                    await hass.async_block_till_done()
                elif kind == "protected_denial":
                    from homeassistant.core import Context

                    from custom_components.uninus_nutriculture.recipes import execute

                    old = hass.config_entries
                    reads = []

                    class Guard:
                        def __getattr__(self, k):
                            return getattr(old, k)

                        def async_get_entry(self, k):
                            reads.append(k)
                            return old.async_get_entry(k)

                    before = serial(dict(entry.options))
                    hass.config_entries = Guard()
                    try:
                        try:
                            await execute(
                                hass,
                                Context(user_id=user.id),
                                "get_recipes_v1",
                                {"config_entry_id": entry.entry_id},
                            )
                        except Exception as e:
                            result = {"denied": type(e).__name__, "target_reads": reads}
                        else:
                            raise AssertionError("unexpected allowed")
                    finally:
                        hass.config_entries = old
                    assert (
                        result["denied"] == "Unauthorized"
                        and reads == []
                        and serial(dict(entry.options)) == before
                    )
                    write(attempt + "/protected-denial.json", result)
                elif kind == "deactivate":
                    await hass.auth.async_deactivate_user(user)
                elif kind == "reactivate":
                    await hass.auth.async_activate_user(user)
                elif kind == "terminal":
                    path = Path(os.environ["P3C_TERMINAL_ROOT"]) / (
                        "p3c-terminal-" + payload + ".json"
                    )
                    terminal = json.loads(path.read_text())
                    assert len(terminal) == 30 and all(
                        v == "off" for v in terminal["output_states"].values()
                    )
                    s = snap()
                    s["status_id"] = "sensor.owned_terminal_" + payload
                    s["states"][s["status_id"]] = {
                        "state": terminal["flow_state"],
                        "attributes": terminal,
                    }
                    # Native capture retains its original entry/targets; no rewritten fields.
                    result = {"snapshot": s}
                    events.append(
                        {
                            "terminal_source": str(path),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                    )
                elif kind == "checkpoint":
                    events.append(payload)
                    write(attempt + "/events.json", events)
                    (OUT / "JOIN_PROGRESS.md").write_text(
                        "# Native S5 join\n"
                        + "\n".join(str(e.get("case", e)) for e in events)
                        + "\n",
                        encoding="utf-8",
                    )
                elif kind == "done":
                    events.append({"case": "browser_done", **payload})
                else:
                    raise ValueError(kind)
            except Exception as e:
                traceback.print_exc()
                result = {"harness_error": str(e)}
            child.stdin.write(json_bytes(result) + b"\n")
            await child.stdin.drain()
        code = await asyncio.wait_for(child.wait(), 10)
        await asyncio.wait_for(drain, 10)
        write(
            attempt + "/result.json",
            {"exit_code": code, "events": events, "native_requests": len(wire)},
        )
        print(
            json.dumps(
                {
                    "attempt": attempt,
                    "exit_code": code,
                    "native_requests": len(wire),
                    "events": [e.get("case", e) for e in events],
                }
            )
        )
        if code:
            raise RuntimeError("browser child failed; inspect stderr and wire")
    finally:
        if child and child.returncode is None:
            child.kill()
            await asyncio.wait_for(child.wait(), 10)
        if child:
            try:
                await asyncio.wait_for(drain, 10)
            except asyncio.TimeoutError, asyncio.CancelledError:
                drain.cancel()
        imports = {}
        for name, module in list(sys.modules.items()):
            path = getattr(module, "__file__", None)
            if path and (
                "custom_components.uninus_nutriculture" in name
                or name
                in (
                    "p2_fixtures",
                    "test_p3_dosing",
                    "test_p3c_flow",
                    "test_p3_stage_projection",
                    "conftest",
                    "test_p2_control",
                    "p3_fixtures",
                )
            ):
                p = Path(path)
                imports[name] = {
                    "path": str(p),
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
        write(attempt + "/actual-imports.json", imports)
        await fixture.aclose()
        await base.aclose()


if __name__ == "__main__":
    asyncio.run(main())
