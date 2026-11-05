import json
import os
import sys
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT.parent / "uninus-nutriculture-card"
OUT = Path(os.environ["P4A_JOIN_OUTPUT"]).resolve()
counter = 0


def rpc(kind, payload=None):
    global counter
    counter += 1
    print(json.dumps({"id": counter, "kind": kind, "payload": payload}), flush=True)
    line = sys.stdin.readline(4 * 1024 * 1024 + 1)
    if len(line) > 4 * 1024 * 1024:
        raise RuntimeError("IPC reply exceeds 4 MiB")
    r = json.loads(line)
    if r.get("harness_error"):
        raise RuntimeError(r["harness_error"])
    return r


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            **(
                {"executable_path": os.environ["CHROMIUM_EXECUTABLE"]}
                if os.environ.get("CHROMIUM_EXECUTABLE")
                else {}
            ),
        )
        try:
            p = browser.new_page(viewport={"width": 768, "height": 1200})
            p.set_default_timeout(7000)
            errors = []
            p.on("pageerror", lambda e: errors.append(str(e)))
            p.set_content('<!doctype html><meta charset="utf-8"><body>')
            p.evaluate("console.log=console.info=console.warn=()=>{}")
            p.expose_function("nativeRPC", rpc)
            p.add_script_tag(path=str(CARD / "uninus-nutriculture-card.js"))
            p.evaluate("""async()=>{
    await customElements.whenDefined('uninus-nutriculture-card');window.cards={};window.receipts=[];window.pending=0;
    window.refreshCard=(name,s)=>{cards[name].hass={states:s.states,services:s.services,user:{id:s.user_id,is_admin:true},connection:{connected:true},callWS:cards[name]._nativeTransport||(cards[name]._nativeTransport=async m=>{pending++;try{const r=await nativeRPC('ws',{name,message:m});receipts.push(r);refreshCard(name,r.snapshot);if(!r.reply.success)throw r.reply.error;return r.reply.result;}finally{pending--}}),callService:()=>{throw Error('unexpected legacy transport')}}};
    window.makeCard=async(name,s)=>{const c=document.createElement('uninus-nutriculture-card');c.id=name;cards[name]=c;document.body.append(c);c.setConfig({entity:s.status_id});refreshCard(name,s);};
    await makeCard('A',(await nativeRPC('snapshot')).snapshot);
   }""")
            a = p.locator("#A")

            def settle():
                p.wait_for_function("pending===0")

            def inspect():
                return rpc("inspect")

            def checkpoint(case, **k):
                rpc("checkpoint", {"case": case, **k})

            def click(c, key):
                c.locator("[data-recipe-" + key + "]").click()
                settle()

            def refresh(c):
                click(c, "refresh")

            before = inspect()
            a.locator("[data-recipe-panel] summary").click()
            p.wait_for_function("cards.A.recipeData!==null")
            settle()
            assert inspect() == before
            assert p.evaluate("cards.A.recipeData.recipes.length") == 0
            checkpoint("native_GET_empty_no_write")
            params = {
                "level_low": 0.4,
                "level_high": 2.5,
                "ph_low": 5.3,
                "ph_high": 5.9,
                "ec_low": 0.6,
                "ec_high": 1.1,
                "refill_timeout": 70,
                "ec_timeout": 80,
                "ph_timeout": 90,
                "mix_duration": 11,
            }
            a.locator("[data-recipe-name]").fill("同名")
            for k, v in params.items():
                a.locator('[data-recipe-parameter="' + k + '"]').fill(str(v))
            click(a, "save")
            saved = inspect()
            rid = p.evaluate("cards.A.recipeData.recipes[0].id")
            assert saved["options"]["recipe_catalog"]["recipes"][0]["parameters"] == params
            assert saved["numbers"] == before["numbers"] and saved["io"] == before["io"]
            assert saved["options"]["settings_revision"] == before["options"]["settings_revision"]
            checkpoint("first_native_SAVE_checkpoint", recipe_id=rid, parameters=params)
            click(a, "apply")
            applied = inspect()
            assert (
                applied["numbers"] == params
                and applied["commit_count"] == saved["commit_count"] + 1
            )
            status = applied["snapshot"]["states"][applied["snapshot"]["status_id"]]["attributes"]
            assert status["parameters"] == params and status["schema_version"] == 5
            assert status["ready_for_irrigation"] is False
            assert all(v == "off" for v in status["output_states"].values())
            protected = {
                k: v
                for k, v in saved["options"].items()
                if k not in ("parameters", "settings_revision", "recipe_catalog")
            }
            assert {
                k: v
                for k, v in applied["options"].items()
                if k not in ("parameters", "settings_revision", "recipe_catalog")
            } == protected
            assert applied["io"] == before["io"]
            checkpoint("Apply_ten_Numbers_S5_one_commit_preserve_nonrecipe_zero_IO", status=status)
            a.locator("[data-recipe-name]").fill("edited")
            click(a, "save")
            edited = inspect()
            assert (
                edited["numbers"] == params
                and edited["options"]["settings_revision"]
                == applied["options"]["settings_revision"]
            )
            a.locator("[data-recipe-name]").fill("cancel draft")
            pre = inspect()
            click(a, "cancel")
            assert inspect() == pre
            assert a.locator("[data-recipe-name]").input_value() == "edited"
            checkpoint("edit_catalog_only_and_Cancel_zero_mutation")
            a.locator("[data-recipe-select]").select_option("")
            a.locator("[data-recipe-name]").fill("edited")
            click(a, "save")
            records = inspect()["options"]["recipe_catalog"]["recipes"]
            assert (
                len(records) == 2
                and records[0]["name"] == records[1]["name"]
                and records[0]["id"] != records[1]["id"]
            )
            checkpoint("same_name_distinct_native_UUIDs")
            pre = inspect()
            click(a, "delete")
            assert inspect() == pre
            click(a, "delete-cancel")
            assert inspect() == pre
            click(a, "delete")
            assert inspect() == pre
            click(a, "delete-confirm")
            assert len(inspect()["options"]["recipe_catalog"]["recipes"]) == 1
            checkpoint("second_delete_confirmation_only_then_native_delete")
            p.evaluate("async()=>{await makeCard('B',(await nativeRPC('snapshot')).snapshot)}")
            b = p.locator("#B")
            b.locator("[data-recipe-panel] summary").click()
            p.wait_for_function("cards.B.recipeData!==null")
            settle()
            refresh(a)
            a.locator("[data-recipe-name]").fill("winner")
            b.locator("[data-recipe-name]").fill("loser draft")
            click(a, "save")
            pre = inspect()
            click(b, "save")
            assert inspect() == pre
            assert b.locator("[data-recipe-name]").input_value() == "loser draft"
            assert "recipe_conflict" in json.dumps(p.evaluate("receipts.at(-1).reply"))
            checkpoint("two_Cards_catalog_CAS_denial_draft_preserved")
            refresh(a)
            refresh(b)
            a.locator("[data-recipe-select]").select_option(rid)
            b.locator("[data-recipe-select]").select_option(rid)
            # Settings changes via real Number service, catalog stays equal for both stale Cards.
            rpc("number_change", 12)
            pre = inspect()
            click(b, "apply")
            assert inspect() == pre
            assert p.evaluate("receipts.at(-1).reply.success") is False
            assert "settings_conflict" in json.dumps(p.evaluate("receipts.at(-1).reply"))
            assert b.locator("[data-recipe-select]").input_value() == rid
            checkpoint("two_Cards_stale_settings_CAS_no_partial_write")
            refresh(a)
            a.locator("[data-recipe-name]").fill("revoked draft")
            pre = inspect()
            rpc("deactivate")
            click(a, "save")
            assert inspect() == pre and not p.evaluate("receipts.at(-1).reply.success")
            assert a.locator("[data-recipe-name]").input_value() == "revoked draft"
            protected = rpc("protected_denial")
            checkpoint(
                "native_active_admin_revoked_denial_and_no_target_metadata_read",
                protected=protected,
            )
            rpc("reactivate")
            refresh(a)
            assert inspect()["io"] == before["io"]
            # SPEC-01 affected native regression: every DTO is produced by registered production APIs.
            for label, name in [
                ("ascii80", "A" * 80),
                ("astral80", "\U0001f331" * 80),
                ("mixed80", "中" * 40 + "\U0001f331" * 40),
            ]:
                pre = inspect()
                old_ids = [r["id"] for r in pre["options"]["recipe_catalog"]["recipes"]]
                a.locator("[data-recipe-select]").select_option("")
                a.locator("[data-recipe-name]").fill(name)
                assert a.locator("[data-recipe-name]").input_value() == name
                click(a, "save")
                created = inspect()
                record = created["options"]["recipe_catalog"]["recipes"][-1]
                unicode_id = record["id"]
                assert record["name"] == name and len(record["name"]) == 80
                assert created["numbers"] == pre["numbers"] and created["io"] == pre["io"]
                assert p.evaluate("cards.A.recipeData.recipes.length") == len(old_ids) + 1
                assert [
                    r["id"] for r in created["options"]["recipe_catalog"]["recipes"][:-1]
                ] == old_ids
                a.locator("[data-recipe-select]").select_option(unicode_id)
                assert a.locator("[data-recipe-name]").input_value() == name
                a.locator("[data-recipe-name]").fill("temporary")
                a.locator("[data-recipe-name]").fill(name)
                click(a, "save")
                assert inspect()["options"]["recipe_catalog"]["recipes"][-1]["name"] == name
                saved_unicode = inspect()
                click(a, "apply")
                native_unicode = inspect()
                assert native_unicode["options"]["recipe_catalog"]["last_applied"]["name"] == name
                assert native_unicode["commit_count"] == saved_unicode["commit_count"] + 1
                assert native_unicode["io"] == pre["io"]
                assert name in a.locator("[data-recipe-history]").inner_text()
                click(a, "delete")
                click(a, "delete-confirm")
                deleted = inspect()
                assert [r["id"] for r in deleted["options"]["recipe_catalog"]["recipes"]] == old_ids
                assert deleted["options"]["recipe_catalog"]["last_applied"]["name"] == name
                assert p.evaluate("cards.A.recipeData!==null")
                assert name in a.locator("[data-recipe-history]").inner_text()
                checkpoint(
                    "SPEC01_native_" + label + "_save_edit_select_apply_delete_history",
                    recipe_id=unicode_id,
                    name=name,
                )
            p.screenshot(path=str(OUT / "final-browser.png"), full_page=True)
            assert not errors, errors
            expected = inspect()
            stored = rpc("store_readback")
            assert stored["options"] == expected["options"]
            assert stored["effective_parameters"] == expected["numbers"]
            checkpoint("normal_STOP_fresh_SDK_process_full_options_catalog_and_parameters_readback")
            rpc("done", {"page_errors": errors, "browser_version": browser.version})
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
