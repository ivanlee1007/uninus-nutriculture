"""Owned adaptation of p4b_quality_browser.py; real Chromium/JSON-lines."""

import json
import os
import sys
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

F = Path(os.environ["P4C_SOURCE"])
OUT = Path(os.environ["P4C_RUN"])
counter = 0


def rpc(kind, payload=None):
    global counter
    counter += 1
    print(json.dumps(dict(id=counter, kind=kind, payload=payload)), flush=True)
    r = json.loads(sys.stdin.readline(4 * 1024 * 1024))
    if "harness_error" in r:
        raise RuntimeError(r["harness_error"])
    return r


def evidence(p, label):
    (OUT / (label + ".dom.json")).write_text(
        json.dumps(
            p.evaluate(
                "({config:window.changed,cache:card.notificationData,result:card.resultNative(),html:card.shadowRoot.innerHTML,calls})"
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    p.screenshot(path=str(OUT / (label + ".png")), full_page=True)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, executable_path=os.environ.get("CHROMIUM_EXECUTABLE")
        )
        p = browser.new_page(viewport={"width": 768, "height": 1200})
        p.set_default_timeout(9000)
        page_errors = []
        p.on("pageerror", lambda error: page_errors.append(str(error)))
        try:
            p.set_content('<!doctype html><meta charset="utf-8"><body>')
            p.evaluate("console.log=console.info=console.warn=console.error=()=>{}")
            p.expose_function("nativeRPC", rpc)
            p.add_script_tag(
                path=str(Path(os.environ["P4C_CARD_REPO"]) / "uninus-nutriculture-card.js")
            )
            p.evaluate("""async()=>{
    window.calls=[];window.card=document.createElement('uninus-nutriculture-card');document.body.append(card);
    window.connection=new EventTarget();connection.connected=true;
    window.publish=s=>{window.lastSnapshot=s;card.hass={states:s.states,services:s.services,user:window.user||(window.user={id:s.user_id,is_admin:true,is_active:true}),connection,callWS:window.ws||(window.ws=async m=>{calls.push(structuredClone(m));const r=await nativeRPC('ws',m);publish(r.snapshot);if(!r.reply.success)throw r.reply.error;return r.reply.result}),callService:()=>{throw Error('unexpected legacy transport')}}};
    publish((await nativeRPC('snapshot')).snapshot);
    window.editor=document.createElement('uninus-nutriculture-card-editor');document.body.append(editor);editor.setConfig({});editor.hass=card.hass;editor.addEventListener('config-changed',e=>window.changed=e.detail.config);
   }""")
            rid = p.evaluate("lastSnapshot.result_id")
            p.locator("[data-result-entity]").evaluate(
                '(e,value)=>e.dispatchEvent(new CustomEvent("value-changed",{detail:{value}}))', rid
            )
            p.evaluate("card.setConfig(changed)")
            assert p.evaluate("changed.result_entity") == rid
            p.locator("[data-result-panel] summary").click()
            p.locator("[data-notification-panel] summary").click()
            p.wait_for_function("!!card.notificationData")
            evidence(p, "firstrealwire")
            rpc(
                "checkpoint",
                {
                    "name": "firstrealwire_editor_native_GET",
                    "cache": p.evaluate("card.notificationData"),
                },
            )
            p.locator("[data-notification-provider]").select_option("persistent_notification")
            p.locator("[data-notification-enabled]").check()
            for k in ["start", "completed"]:
                p.locator('[data-notification-event="' + k + '"]').check()
            p.locator("[data-notification-cooldown]").fill("600")
            p.locator("[data-notification-save]").click()
            p.wait_for_function("!card.notificationOperation")
            evidence(p, "save")
            assert "已保存並讀回" in p.locator("[data-notification-message]").inner_text()
            assert p.evaluate('calls.map(m=>m.type.split("/").at(-1))') == ["get", "save", "get"]
            rpc("verify_store", p.evaluate("card.notificationData"))
            rpc("checkpoint", {"name": "Card_Save_automatic_GET_physical_Store"})
            p.locator("[data-notification-cooldown]").fill("800")
            p.locator("[data-notification-cancel]").click()
            assert p.locator("[data-notification-cooldown]").input_value() == "600"
            rpc("native_options")
            p.locator("[data-notification-get]").click()
            p.wait_for_function("!card.notificationOperation")
            full = rpc("drive")
            p.evaluate("(s)=>publish(s)", full["snapshot"])
            p.wait_for_function('card.resultNative()?.last_result?.state==="completed"')
            assert "completed" in p.locator("[data-result-status]").inner_text()
            p.locator("[data-notification-get]").click()
            p.wait_for_function("!card.notificationOperation")
            evidence(p, "terminal")
            rpc(
                "checkpoint",
                {
                    "name": "four_stage_result_native_API_Card",
                    "result": p.evaluate("card.resultNative()"),
                    "notification": p.evaluate("card.notificationData"),
                    "status": p.locator("[data-result-status]").inner_text(),
                },
            )
            assert not page_errors
            rpc("done", {"browser": browser.version, "page_errors": page_errors})
        except BaseException:
            try:
                evidence(p, "failure")
            except BaseException:
                pass
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
