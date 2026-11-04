"""Replay unmodified native post-run states through the shipped strict Card."""

import hashlib
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    capture = Path(sys.argv[1])
    shipped = (
        Path(__file__).resolve().parents[2] / "uninus-nutriculture-card/uninus-nutriculture-card.js"
    )
    data = json.loads(capture.read_text())
    with sync_playwright() as p:
        options = {"headless": True}
        if os.environ.get("CHROMIUM_EXECUTABLE"):
            options["executable_path"] = os.environ["CHROMIUM_EXECUTABLE"]
        browser = p.chromium.launch(**options)
        try:
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content("<html><body></body></html>")
            page.add_script_tag(path=str(shipped))
            page.evaluate(
                """data=>{
                window.calls=[];window.card=document.createElement('uninus-nutriculture-card');
                document.body.append(card);card.setConfig({entity:data.status_id});
                card.hass={states:data.states,callService:(...args)=>{
                    calls.push(args);return Promise.resolve({applied:true});}};
            }""",
                data,
            )
            assert page.evaluate("card.controls.isConnected"), (
                "native stage rejected by shipped strict consumer"
            )
            for key in ("automation_enabled", "emergency_stop", "reset_fault"):
                assert not page.evaluate("key=>card.controlRows.get(key).button.disabled", key)
            page.locator('[data-control="automation_enabled"] button').click()
            page.evaluate("card.details.open=true")
            page.locator('[data-param="ph_low"] input').fill("5.3")
            assert not page.locator("[data-group-apply]").is_disabled()
            page.locator("[data-group-apply]").click()
            calls = page.evaluate("calls")
            assert len(calls) == 2
            assert calls[0][0:2] == ["switch", "turn_on"]
            assert calls[1][0:2] == ["uninus_nutriculture", "apply_control_settings"]
            assert not errors, errors
            print(
                json.dumps(
                    {
                        "browser": browser.version,
                        "calls": calls,
                        "page_errors": errors,
                        "shipped_sha256": hashlib.sha256(shipped.read_bytes()).hexdigest(),
                        "native_sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
                    }
                )
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
