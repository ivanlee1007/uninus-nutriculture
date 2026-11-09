"""P5a real visual controls -> unchanged native callWS; no product fallbacks."""

import json
import os
import queue
import sys
import threading
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT.parent / "uninus-nutriculture-card" / "uninus-nutriculture-card.js"
COUNTER = 0
INBOX = queue.Queue()


def stdin_lines():
    for line in sys.stdin:
        INBOX.put(line)
    INBOX.put(None)


threading.Thread(target=stdin_lines, daemon=True).start()


def rpc(kind, payload=None):
    global COUNTER
    COUNTER += 1
    print(json.dumps({"id": COUNTER, "kind": kind, "payload": payload}), flush=True)
    line = INBOX.get(timeout=65 if kind == "fresh_sdk" else 15)
    if line is None:
        raise RuntimeError("native parent EOF")
    result = json.loads(line)
    if "harness_error" in result:
        raise RuntimeError(result["harness_error"])
    return result


def unchanged(before, after):
    for key in ("options", "io", "commit_count", "disk"):
        assert before[key] == after[key], (key, before[key], after[key])


def authoritative(result, payload):
    options = result["options"]
    attr = result["snapshot"]["states"][result["snapshot"]["status_id"]]["attributes"]
    assert options["flow_plan"] == payload["flow_plan"] == attr["flow_plan"]
    assert options["control"]["allowed_weekdays"] == payload["allowed_weekdays"]
    assert attr["allowed_weekdays"] == payload["allowed_weekdays"]
    for key in ("settings_revision", "flow_plan_revision"):
        assert attr[key] == options[key]


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, executable_path=os.environ.get("CHROMIUM_EXECUTABLE") or None
        )
        try:
            page = browser.new_page(viewport={"width": 768, "height": 1100})
            page.set_default_timeout(10000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content('<!doctype html><meta charset="utf-8"><body>')
            # Every console channel goes to the owned stderr, never JSONL stdout.
            page.on("console", lambda message: print(message.text, file=sys.stderr))
            page.evaluate(
                "window.addEventListener('unhandledrejection',e=>console.error(String(e.reason)))"
            )
            page.expose_function("nativeRPC", rpc)
            page.add_script_tag(path=str(CARD))
            page.evaluate("""async()=>{
              await customElements.whenDefined('uninus-nutriculture-card');
              window.cards={};window.receipts=[];window.pending=0;
              window.push=(name,s)=>{
                const c=cards[name];c.hass={...c.hassState,states:s.states};
              };
              window.makeCard=async(name,s)=>{
                const c=document.createElement('uninus-nutriculture-card');
                c.id=name;cards[name]=c;document.body.append(c);
                const callWS=async message=>{
                  pending++;
                  try {
                    const r=await nativeRPC('ws',{principal_id:s.user_id,message});
                    receipts.push({message,reply:r.reply});push(name,r.snapshot);
                    if(!r.reply.success)throw r.reply.error;
                    return r.reply.result;
                  } finally {pending--;}
                };
                c.hassState={user:{id:s.user_id,is_admin:true},
                  connection:{connected:true},services:s.services,callWS};
                c.setConfig({entity:s.status_id});push(name,s);
              };
              await makeCard('A',(await nativeRPC('snapshot')).snapshot);
            }""")
            a = page.locator("#A")
            assert a.locator("[data-flow-row]").count() == 4
            smoke = rpc("smoke_registered")
            assert smoke["reply"]["success"], smoke
            assert "response" in smoke["reply"]["result"]
            rpc(
                "checkpoint",
                {"case": "native_auth_setup_registered_smoke", "browser": browser.version},
            )
            # Desired behavior assertion, identical on baseline and integrated Card.
            for stage, label in (
                ("refill", "編輯補水"),
                ("nutrient", "編輯加養"),
                ("acid", "編輯加酸"),
                ("mix", "編輯獨立攪拌"),
            ):
                button = a.locator(f'[data-plan-stage="{stage}"]').get_by_role(
                    "button", name=label, exact=True
                )
                assert button.count() == 1, f"missing operable visual stage button: {stage}/{label}"
                button.click()
                assert page.evaluate(
                    """stage=>cards.A.shadowRoot.activeElement===
                  cards.A.shadowRoot.querySelector(`[data-flow-row="${stage}"] [data-flow-field="start_rule"]`)""",
                    stage,
                )
                assert (
                    page.evaluate("cards.A.shadowRoot.activeElement.dataset.flowField")
                    == "start_rule"
                )
            rpc("checkpoint", {"case": "visual_buttons_focus_existing_rules"})

            def settle():
                page.wait_for_function("pending===0")

            def field(stage, key):
                return a.locator(f'[data-flow-row="{stage}"] [data-flow-field="{key}"]')

            before = rpc("inspect")
            # Preview and Cancel of a real changed draft must be read-only.
            field("acid", "delay_seconds").fill("8")
            a.locator("[data-plan-preview]").click()
            settle()
            assert a.locator("[data-preview-day]").count() == 7
            unchanged(before, rpc("inspect"))
            a.locator("[data-plan-cancel]").click()
            unchanged(before, rpc("inspect"))
            assert a.locator("[data-preview-day]").count() == 0

            a.locator('[data-plan-stage="acid"]').get_by_role(
                "button", name="編輯加酸", exact=True
            ).click()
            a.locator('[data-flow-row="acid"] [data-move="up"]').click()
            field("acid", "start_rule").select_option("after_previous_started")
            field("acid", "delay_seconds").fill("12")
            field("acid", "wait_timeout_seconds").fill("45")
            field("acid", "source").select_option("level")
            field("acid", "operator").select_option("gte")
            field("acid", "value").fill("0.5")
            for checkbox in a.locator('[data-flow-row="mix"] [data-flow-day]').all():
                checkbox.uncheck()
            a.locator('[data-flow-row="acid"] [data-flow-day="sun"]').uncheck()
            a.locator("[data-run-timeout]").fill("130")
            draft = page.evaluate("structuredClone(cards.A.planPayload(cards.A.planDraft))")
            assert [row["stage"] for row in draft["flow_plan"]["rows"]] == [
                "refill",
                "mix",
                "acid",
                "nutrient",
            ]
            assert draft["allowed_weekdays"]["mix"] == []
            acid = draft["flow_plan"]["rows"][2]
            assert acid == dict(
                stage="acid",
                start_rule="after_previous_started",
                delay_seconds=12,
                wait_timeout_seconds=45,
                condition=dict(source="level", operator="gte", value=0.5),
            )
            start = page.evaluate("receipts.length")
            a.locator("[data-plan-preview]").click()
            settle()
            previews = page.evaluate("receipts.slice(%d)" % start)
            assert len(previews) == 7
            assert {row["message"]["service_data"]["weekday"] for row in previews} == {
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
                "sat",
                "sun",
            }
            for row in previews:
                message = row["message"]
                assert message["service"] == "preview_flow_plan_v5"
                assert message["return_response"] is True
                assert {k: v for k, v in message["service_data"].items() if k != "weekday"} == draft
                assert row["reply"]["success"]
            unchanged(before, rpc("inspect"))
            assert a.locator("[data-preview-day]").count() == 7
            rpc("checkpoint", {"case": "seven_real_preview_cancel_zero_commit_zero_io"})
            a.locator("[data-plan-apply]").click()
            settle()
            page.wait_for_function("cards.A.planDraft===null && cards.A.planOperation===null")
            saved = rpc("inspect")
            authoritative(saved, draft)
            reply = page.evaluate("receipts.at(-1).reply")
            assert reply["success"] and reply["result"]["response"]["applied"]
            for key in ("settings_revision", "flow_plan_revision"):
                assert saved["options"][key] == before["options"][key] + 1
                assert reply["result"]["response"][key] == saved["options"][key]
            assert saved["commit_count"] == before["commit_count"] + 1
            assert saved["io"] == before["io"]
            assert saved["options"]["control"] == {
                **before["options"]["control"],
                "allowed_weekdays": draft["allowed_weekdays"],
            }
            allowed = {"flow_plan", "flow_plan_revision", "settings_revision", "control"}
            assert {k: v for k, v in saved["options"].items() if k not in allowed} == {
                k: v for k, v in before["options"].items() if k not in allowed
            }
            rpc("checkpoint", {"case": "single_atomic_apply_response_native_full_equality"})

            page.evaluate(
                "async()=>{cards.A.remove();await makeCard('A',(await nativeRPC('snapshot')).snapshot)}"
            )
            assert field("acid", "delay_seconds").input_value() == "12"
            assert all(
                not checkbox.is_checked()
                for checkbox in a.locator('[data-flow-row="mix"] [data-flow-day]').all()
            )
            rpc("options_preview_cancel")
            # Stale Options: true native FlowManager CAS, not a mocked error.
            rpc("options_hold")
            field("acid", "delay_seconds").fill("13")
            a.locator("[data-plan-apply]").click()
            settle()
            page.wait_for_function("cards.A.planDraft===null")
            rpc("options_stale")
            options = rpc("options_save")
            page.evaluate("s=>push('A',s)", options["snapshot"])
            authoritative(
                options,
                {
                    "flow_plan": options["options"]["flow_plan"],
                    "allowed_weekdays": options["options"]["control"]["allowed_weekdays"],
                },
            )
            assert a.locator('[data-flow-row="acid"] [data-flow-day="sun"]').is_checked()
            rpc("checkpoint", {"case": "native_options_preview_cancel_save_and_stale"})

            page.evaluate("async()=>{await makeCard('B',(await nativeRPC('snapshot')).snapshot)}")
            field("acid", "delay_seconds").fill("14")
            baseline = page.evaluate("structuredClone(cards.A.planDraft)")
            b = page.locator("#B")
            b.locator('[data-flow-row="acid"] [data-flow-field="delay_seconds"]').fill("15")
            b.locator("[data-plan-apply]").click()
            settle()
            winner = rpc("inspect")
            assert a.locator("[data-plan-apply]").is_enabled()
            a.locator("[data-plan-apply]").click()
            settle()
            unchanged(winner, rpc("inspect"))
            assert page.evaluate("receipts.at(-1).reply.success") is False
            assert page.evaluate("structuredClone(cards.A.planDraft)") == baseline
            assert field("acid", "delay_seconds").input_value() == "14"
            rpc("checkpoint", {"case": "real_two_card_dual_cas_loser_dirty_not_rebased"})
            stored = rpc("store_readback")
            assert stored["options"] == winner["options"]
            fresh = rpc("fresh_sdk")
            assert fresh["options"] == winner["options"]
            assert not errors, errors
            rpc("done", {"page_errors": errors})
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
