"""Shipped schema3 native controls -> isolated native nutrient execution.

The HTML supplies only the browser's HA object/transport, not backend responses.
All entity attributes and revisions come from isolated real Core handlers.
"""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def browser_probe(url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        opts = {"headless": True}
        if os.environ.get("CHROMIUM_EXECUTABLE"):
            opts["executable_path"] = os.environ["CHROMIUM_EXECUTABLE"]
        browser = p.chromium.launch(**opts)
        page = browser.new_page(viewport={"width": 768, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        page.wait_for_function("window.ready === true")

        def command(route):
            page.evaluate("async route=>await backend(route,{})", route)

        def wait_for(expression, timeout=5):
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                command("refresh")
                if page.evaluate(expression):
                    return
                page.wait_for_timeout(20)
            raise AssertionError("Native state deadline: " + expression)

        for index, key in enumerate(("automation_enabled", "nutrient_enabled", "flow_run"), 1):
            page.locator(f'[data-control="{key}"] button').click()
            page.wait_for_function("n=>completed===n", arg=index)
        wait_for("realStates[entity].attributes.output_states.nutrient==='on'")
        assert page.evaluate("realStates[entity].attributes.output_states.circulation") == "on"
        command("mean")
        wait_for("realStates[entity].attributes.output_states.nutrient==='off'")
        assert page.evaluate("realStates[entity].attributes.output_states.circulation") == "on"
        wait_for("['waiting_sample','stabilizing'].includes(realStates[entity].state)")
        command("sample")
        wait_for("realStates[entity].state==='completed'")
        assert page.evaluate("realStates[entity].attributes.output_states.circulation") == "off"
        assert (
            page.evaluate(
                "realStates[realStates[entity].attributes.control_entities.flow_run].state"
            )
            == "off"
        )
        assert page.evaluate("realStates[entity].attributes.ready_for_irrigation") is False
        assert not errors, errors
        result = {
            "browser": browser.version,
            "ui_native_actions": 3,
            "midpoint_stopped": True,
            "required_mix_retained": True,
            "fresh_sample_completed": True,
            "page_errors": errors,
        }
        browser.close()
        print(json.dumps(result))


async def native_probe(card_path, browser_python, output):
    sys.path.insert(0, str(ROOT / "tests"))
    from homeassistant.auth import auth_manager_from_config
    from homeassistant.auth.const import GROUP_ID_ADMIN
    from homeassistant.core import Context
    from p2_fixtures import control_hass
    from p3_fixtures import nutrient_payload
    from test_p2_control import add_tank, target
    from test_p3_dosing import dosing_hass

    output.mkdir(parents=True, exist_ok=False)

    def input_hashes():
        paths = [
            path
            for folder in (ROOT / "custom_components", ROOT / "tests")
            for path in folder.rglob("*")
            if path.is_file() and path.suffix in {".py", ".json", ".yaml"}
        ]
        paths.extend((Path(__file__).resolve(), card_path))
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

    before = input_hashes()
    scratch = Path(os.environ.get("TMPDIR", str(Path.home() / ".hermes/cache/scratch")))
    with tempfile.TemporaryDirectory(prefix="p3a-dosing-", dir=scratch) as temp:
        base_fixture = control_hass.__wrapped__(Path(temp))
        hass = await anext(base_fixture)
        fixture = dosing_hass.__wrapped__(hass)
        await anext(fixture)
        server = None
        try:
            entry = await add_tank(hass)
            values = nutrient_payload(hass)
            values.pop("refill_output")
            values.update(
                commissioned=False,
                feedback_timeout=1,
                device_max_on_seconds=3,
                pulse_seconds=2,
                post_mix_seconds=1,
                sample_wait_timeout_seconds=5,
                stable_samples=1,
                stable_interval_seconds=1,
                flow_timeout_seconds=15,
            )
            form = await hass.config_entries.options.async_init(entry.entry_id)
            await hass.config_entries.options.async_configure(form["flow_id"], values)
            await hass.async_block_till_done()
            hass.states.async_set("sensor.ec", "0.7", {"unit_of_measurement": "mS/cm"})
            hass.auth = await auth_manager_from_config(hass, [], [])
            admin = await hass.auth.async_create_user(
                "Isolated bridge admin", group_ids=[GROUP_ID_ADMIN]
            )
            context = Context(user_id=admin.id)
            entity = target(hass, entry, "sensor", "control_status")
            assert hass.states.get(entity).attributes["schema_version"] == 3
            assert hass.states.get(entity).attributes["capabilities"]["nutrient"] is True
            prefix = "/" + secrets.token_urlsafe(24) + "/"
            calls = []
            mean_at = None

            def snapshot():
                return {
                    "entity": entity,
                    "states": {
                        s.entity_id: {"state": s.state, "attributes": dict(s.attributes)}
                        for s in hass.states.async_all()
                    },
                }

            html = """<!doctype html><meta charset="utf-8"><script src="card.js"></script>
<uninus-nutriculture-card></uninus-nutriculture-card><script>
window.ready=false;window.completed=0;window.card=document.querySelector('uninus-nutriculture-card');
window.backend=async(route,payload)=>{
 const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const d=await r.json();if(d.error)throw new Error(d.error);window.entity=d.entity;window.realStates=d.states;
 card.hass={states:d.states,callService:async(domain,service,data)=>{try{return await backend('call',{domain,service,data})}finally{completed++}}};return d;
};(async()=>{const d=await backend('refresh',{});card.setConfig({entity:d.entity});card.hass=card.hass;ready=true})()
</script>"""

            async def handle(reader, writer):
                nonlocal mean_at
                content_type = "application/json"
                try:
                    head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
                    first, *headers = head.decode().split("\r\n")
                    method, path, _ = first.split()
                    length = next(
                        (
                            int(h.split(":", 1)[1])
                            for h in headers
                            if h.lower().startswith("content-length:")
                        ),
                        0,
                    )
                    if length > 16384 or not path.startswith(prefix):
                        raise ValueError("invalid probe request")
                    route = path[len(prefix) :]
                    data = json.loads(await reader.readexactly(length)) if length else {}
                    if route == "card.js" and method == "GET":
                        body, content_type = card_path.read_bytes(), "text/javascript"
                    elif route == "" and method == "GET":
                        body, content_type = html.encode(), "text/html; charset=utf-8"
                    else:
                        if route == "call" and method == "POST":
                            assert (data["domain"], data["service"]) in {
                                ("switch", "turn_on"),
                                ("switch", "turn_off"),
                                ("button", "press"),
                            }
                            controls = hass.states.get(entity).attributes["control_entities"]
                            assert data["data"]["entity_id"] in controls.values()
                            calls.append(data)
                            await hass.services.async_call(
                                data["domain"],
                                data["service"],
                                data["data"],
                                blocking=True,
                                context=context,
                            )
                        elif route in {"mean", "sample"} and method == "POST":
                            from homeassistant.util import dt as dt_util

                            if route == "mean":
                                pump = hass.data["p3_fixture"]["outputs"][0]
                                assert hass.states.get(pump.entity_id).state == "on"
                                mean_at = dt_util.utcnow()
                            hass.states.async_set(
                                "sensor.ec",
                                "0.85" if route == "mean" else "0.86",
                                {"unit_of_measurement": "mS/cm"},
                            )
                        elif route != "refresh" or method != "POST":
                            raise ValueError("unknown probe route")
                        await hass.async_block_till_done()
                        body = json.dumps(snapshot()).encode()
                except Exception as error:
                    body = json.dumps({"error": str(error)}).encode()
                writer.write(
                    f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
                writer.close()
                await writer.wait_closed()

            server = await asyncio.start_server(handle, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            process = await asyncio.create_subprocess_exec(
                str(browser_python),
                str(Path(__file__).resolve()),
                "--browser",
                f"http://127.0.0.1:{port}{prefix}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), 90)
            except BaseException:
                process.kill()
                await process.communicate()
                raise
            (output / "browser.stdout").write_bytes(stdout)
            (output / "browser.stderr").write_bytes(stderr)
            (output / "native-diagnostic.json").write_text(
                json.dumps(
                    {
                        "browser_returncode": process.returncode,
                        "actual_native_calls": calls,
                        "hardware_calls": hass.data["p3_fixture"]["calls"],
                        "snapshot": snapshot(),
                        "flow_state": entry.runtime_data.control.flow_state,
                        "fault": entry.runtime_data.control.fault,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            assert process.returncode == 0, stderr.decode(errors="replace")
            browser_result = json.loads(stdout.decode().splitlines()[-1])
            assert len(calls) == 3 and mean_at is not None
            hardware = hass.data["p3_fixture"]["calls"]
            assert hardware[:2] == [("circulation", "on"), ("nutrient", "on")]
            assert hardware.count(("nutrient", "on")) == 1
            assert not any(event[1] == "device_local_cutoff" for event in hardware)
            pump, circulation = hass.data["p3_fixture"]["outputs"]
            assert hass.states.get(pump.entity_id).state == "off"
            assert hass.states.get(circulation.entity_id).state == "off"
            reaction_seconds = (
                hass.states.get(pump.entity_id).last_changed - mean_at
            ).total_seconds()
            assert 0 <= reaction_seconds < 0.75, reaction_seconds
            assert not hass.data["p2_fixture"]["calls"], "Nutrient-only must never actuate refill"
            assert not entry.runtime_data.control.running
            after = input_hashes()
            assert before == after, "Source inputs changed during the bridge"
            (output / "source-manifest.json").write_text(
                json.dumps({"before": before, "after": after, "unchanged": True}, indent=2),
                encoding="utf-8",
            )
            receipt = {
                "shipped_card_sha256": hashlib.sha256(card_path.read_bytes()).hexdigest(),
                "browser": browser_result,
                "actual_native_calls": calls,
                "all_hardware_calls": hardware,
                "midpoint_off_seconds": reaction_seconds,
                "engine_supported": True,
                "physical_device_test": False,
                "external_ha_access": False,
            }
            (output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            print(json.dumps(receipt))
        finally:
            if server:
                server.close()
                await server.wait_closed()
            await fixture.aclose()
            await base_fixture.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser")
    parser.add_argument("--card", type=Path)
    parser.add_argument("--browser-python", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.browser:
        browser_probe(args.browser)
    else:
        asyncio.run(native_probe(args.card, args.browser_python, args.output))
