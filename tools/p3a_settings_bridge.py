"""Shipped schema3 group editor -> native HA service; no actuation or live HA.

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
        page.evaluate("card.details.open=true")
        low = page.locator('[data-param="ec_low"] input')
        high = page.locator('[data-param="ec_high"] input')
        low.fill("0.85")
        page.locator("[data-group-cancel]").click()
        assert page.evaluate("completed") == 0
        assert low.input_value() == "0.8"
        low.fill("0.9")
        high.fill("1.1")
        page.locator("[data-group-apply]").click()
        page.wait_for_function("completed === 1")
        page.wait_for_function("card.groupMessage.textContent.includes('已套用')")
        assert page.evaluate("realStates[entity].attributes.settings_revision") == 2
        assert low.input_value() == "0.9" and high.input_value() == "1.1"
        page.evaluate("card.details.open=false;card.details.open=true")
        assert low.input_value() == "0.9"
        low.fill("0.85")
        page.evaluate("async()=>{await backend('advance',{})}")
        assert "settings_conflict" in page.locator("[data-group-message]").inner_text()
        assert page.locator("[data-group-apply]").is_disabled()
        assert low.input_value() == "0.85"
        page.locator("[data-group-cancel]").click()
        assert low.input_value() == "0.9"
        assert page.locator('[data-param="ph_low"] input').input_value() == "5.5"
        assert page.evaluate("completed") == 1
        assert not errors, errors
        result = {
            "browser": browser.version,
            "ui_group_apply": 1,
            "cancel_zero_service": True,
            "revision_value_readback": True,
            "native_number_conflict_preserves_draft": True,
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
    from p3_fixtures import commission, nutrient_hass
    from test_p2_control import add_tank, target

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
    with tempfile.TemporaryDirectory(prefix="p3a-settings-", dir=scratch) as temp:
        base_fixture = control_hass.__wrapped__(Path(temp))
        hass = await anext(base_fixture)
        fixture = nutrient_hass.__wrapped__(hass)
        await anext(fixture)
        server = None
        try:
            entry = await add_tank(hass)
            await commission(hass, entry)
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
                            assert (data["domain"], data["service"]) == (
                                "uninus_nutriculture",
                                "apply_control_settings",
                            )
                            assert data["data"]["config_entry_id"] == entry.entry_id
                            calls.append(data)
                            await hass.services.async_call(
                                data["domain"],
                                data["service"],
                                data["data"],
                                blocking=True,
                                context=context,
                            )
                        elif route == "advance" and method == "POST":
                            await hass.services.async_call(
                                "number",
                                "set_value",
                                {
                                    "entity_id": target(hass, entry, "number", "ph_low"),
                                    "value": 5.5,
                                },
                                blocking=True,
                                context=context,
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
            assert process.returncode == 0, stderr.decode(errors="replace")
            browser_result = json.loads(stdout.decode().splitlines()[-1])
            assert len(calls) == 1 and entry.options["settings_revision"] == 3
            assert entry.options["parameters"]["ec_low"] == 0.9
            assert entry.options["parameters"]["ec_high"] == 1.1
            assert not hass.data["p3_fixture"]["calls"] and not hass.data["p2_fixture"]["calls"]
            assert not entry.runtime_data.control.running and not entry.runtime_data.control.master
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
                "settings_revision": 3,
                "all_hardware_calls": [],
                "engine_supported": hass.states.get(entity).attributes["capabilities"]["nutrient"],
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
