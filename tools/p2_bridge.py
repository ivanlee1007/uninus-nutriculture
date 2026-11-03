"""Shipped Card -> isolated native HA -> native SwitchEntity bridge.

Only binds an ephemeral loopback listener and uses the existing P2 fake hardware.
Not a live HA dashboard, REST-auth, commissioning or physical-device acceptance.
"""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def browser_probe(base):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        options = {"headless": True}
        if os.environ.get("CHROMIUM_EXECUTABLE"):
            options["executable_path"] = os.environ["CHROMIUM_EXECUTABLE"]
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 768, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base)
        page.wait_for_function("window.bridgeReady === true")

        def click(key):
            before = page.evaluate("window.completed")
            page.locator(f'[data-control="{key}"] button').click()
            page.wait_for_function("n => window.completed > n", arg=before)
            assert not page.evaluate("window.lastError"), page.evaluate("window.lastError")

        def state(key):
            return page.evaluate(
                "k => window.realStates[window.realStates[window.entity].attributes.control_entities[k]].state",
                key,
            )

        def command(route):
            page.evaluate("async r => { await window.backend(r, {}); }", route)

        assert state("automation_enabled") == "off"
        click("automation_enabled")
        click("refill_enabled")
        click("flow_run")
        assert state("flow_run") == "on"
        command("high")
        assert state("flow_run") == "off"
        assert page.evaluate("window.realStates[window.entity].state") == "completed"
        command("low")
        click("flow_run")
        click("flow_run")
        assert state("flow_run") == "off"
        click("flow_run")
        click("emergency_stop")
        assert state("automation_enabled") == "off"
        assert state("flow_run") == "off"
        assert (
            page.evaluate("window.realStates[window.entity].attributes.fault") == "emergency_stop"
        )
        click("reset_fault")
        assert state("automation_enabled") == "off"
        assert page.evaluate("window.realStates[window.entity].attributes.fault") is None
        click("automation_enabled")
        command("external")
        assert state("flow_run") == "on"
        click("flow_run")
        assert state("flow_run") == "off"
        assert (
            page.evaluate("window.realStates[window.entity].attributes.ready_for_irrigation")
            is False
        )
        assert not errors, errors
        result = {
            "browser": browser.version,
            "mapped_ui_actions": page.evaluate("window.completed"),
            "page_errors": errors,
            "high_water": True,
            "normal_stop": True,
            "emergency_reset": True,
            "external_service_readback": True,
        }
        browser.close()
        print(json.dumps(result))


async def native_probe(card_path, browser_python, output):
    sys.path.insert(0, str(ROOT / "tests"))
    from homeassistant.auth import auth_manager_from_config
    from homeassistant.auth.const import GROUP_ID_ADMIN
    from homeassistant.core import Context
    from p2_fixtures import control_hass
    from test_p2_control import add_tank, configure, target

    output.mkdir(parents=True, exist_ok=False)
    temporary_root = Path(os.environ.get("TMPDIR", str(Path.home() / ".hermes/cache/scratch")))
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p2-native-bridge-", dir=temporary_root) as temporary:
        fixture = control_hass.__wrapped__(Path(temporary))
        hass = await anext(fixture)
        server = None
        try:
            tank = await add_tank(hass)
            await configure(hass, tank)
            hass.auth = await auth_manager_from_config(hass, [], [])
            admin = await hass.auth.async_create_user(
                "Isolated bridge admin", group_ids=[GROUP_ID_ADMIN]
            )
            context = Context(user_id=admin.id)
            entity = target(hass, tank, "sensor", "control_status")
            assert entity
            assert not hass.data["p2_fixture"]["calls"]
            namespace = "/p2/" + secrets.token_urlsafe(24) + "/"
            calls = []

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
window.completed=0; window.lastError=''; window.bridgeReady=false;
window.card=document.querySelector('uninus-nutriculture-card');
window.backend=async function(route, payload) {
 const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const d=await r.json(); if(d.error) throw new Error(d.error);
 window.entity=d.entity; window.realStates=d.states;
 card.hass={states:d.states,callService:async function(domain,service,data){
   window.lastError=''; try {await window.backend('call',{domain,service,data});}
   catch(e){window.lastError=String(e);throw e;} finally{window.completed++;}
 }}; return d;
};
(async()=>{const r=await fetch('state');const d=await r.json();window.entity=d.entity;
 card.setConfig({type:'custom:uninus-nutriculture-card',entity:d.entity});
 await window.backend('refresh',{});window.bridgeReady=true;})()
</script>"""

            async def handle(reader, writer):
                status = 200
                content_type = "application/json"
                try:
                    header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
                    first, *headers = header.decode().split("\r\n")
                    method, path, _ = first.split()
                    length = next(
                        (
                            int(h.split(":", 1)[1])
                            for h in headers
                            if h.lower().startswith("content-length:")
                        ),
                        0,
                    )
                    if length > 4096 or not path.startswith(namespace):
                        raise ValueError("unknown probe route")
                    route = path[len(namespace) :]
                    payload = json.loads(await reader.readexactly(length)) if length else {}
                    if route == "card.js" and method == "GET":
                        body = card_path.read_bytes()
                        content_type = "text/javascript"
                    elif route == "" and method == "GET":
                        body = html.encode()
                        content_type = "text/html; charset=utf-8"
                    else:
                        if route == "call" and method == "POST":
                            controls = hass.states.get(entity).attributes["control_entities"]
                            domain, service, data = (
                                payload["domain"],
                                payload["service"],
                                payload["data"],
                            )
                            assert data.get("entity_id") in controls.values()
                            assert (domain, service) in {
                                ("switch", "turn_on"),
                                ("switch", "turn_off"),
                                ("button", "press"),
                            }
                            calls.append(payload)
                            await hass.services.async_call(
                                domain, service, data, blocking=True, context=context
                            )
                        elif route in {"high", "low"} and method == "POST":
                            hass.states.async_set(
                                "sensor.level",
                                2.5 if route == "high" else 2,
                                {"unit_of_measurement": "m"},
                            )
                        elif route == "external" and method == "POST":
                            result = await hass.services.async_call(
                                "uninus_nutriculture",
                                "start_flow",
                                {"config_entry_id": tank.entry_id},
                                blocking=True,
                                return_response=True,
                                context=context,
                            )
                            assert result["accepted"] is True and result["run_id"]
                        elif route not in {"state", "refresh"}:
                            raise ValueError("unknown probe operation")
                        await hass.async_block_till_done()
                        body = json.dumps(snapshot(), default=str).encode()
                except Exception as error:
                    status = 400
                    body = json.dumps({"error": str(error)}).encode()
                writer.write(
                    f"HTTP/1.1 {status} OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
                writer.close()
                await writer.wait_closed()

            server = await asyncio.start_server(handle, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            base = f"http://127.0.0.1:{port}{namespace}"
            process = await asyncio.create_subprocess_exec(
                str(browser_python),
                str(Path(__file__).resolve()),
                "--browser",
                base,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), 90)
            (output / "browser.stdout.log").write_bytes(stdout)
            (output / "browser.stderr.log").write_bytes(stderr)
            assert process.returncode == 0, stderr.decode(errors="replace")
            browser_result = json.loads(stdout)
            hardware = hass.data["p2_fixture"]
            actions = [c[0] for c in hardware["calls"]]
            assert actions == ["turn_on", "turn_off"] * 4, actions
            assert hass.states.get(hardware["hardware"].entity_id).state == "off"
            assert not tank.runtime_data.control.running
            receipt = {
                "shipped_card_sha256": hashlib.sha256(card_path.read_bytes()).hexdigest(),
                "browser": browser_result,
                "native_mapped_calls": calls,
                "actual_hardware_actions": actions,
                "active_run": False,
                "physical_device_test": False,
                "external_ha_access": False,
            }
            (output / "receipt.json").write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(receipt, ensure_ascii=False))
        finally:
            if server:
                server.close()
                await server.wait_closed()
            await fixture.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser")
    parser.add_argument("--card", type=Path)
    parser.add_argument("--browser-python", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.browser:
        browser_probe(args.browser)
    else:
        assert args.card and args.card.is_file()
        assert args.browser_python and args.browser_python.is_file()
        assert args.output
        asyncio.run(native_probe(args.card, args.browser_python, args.output))


if __name__ == "__main__":
    main()
