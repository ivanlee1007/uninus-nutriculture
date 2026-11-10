"""Portable P5a default producer and strict private-receipt verifier; safe export only."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

B = Path(__file__).resolve().parents[1]
C = B.parent / "uninus-nutriculture-card"
BUNDLE = "591eb021ebf0117d0cab48297603409807672c2b423c9eb15c7dd1ce384c670b"
CASES = [
    "native_auth_setup_registered_smoke",
    "visual_buttons_focus_existing_rules",
    "seven_real_preview_cancel_zero_commit_zero_io",
    "single_atomic_apply_response_native_full_equality",
    "native_options_preview_cancel_save_and_stale",
    "real_two_card_dual_cas_loser_dirty_not_rebased",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def unchanged(before, after):
    for key in ("options", "io", "commit_count", "disk"):
        assert before[key] == after[key], key


def truth(row):
    options = row["options"]
    snap = row["snapshot"]
    attrs = snap["states"][snap["status_id"]]["attributes"]
    assert attrs["flow_plan"] == options["flow_plan"]
    assert attrs["allowed_weekdays"] == options["control"]["allowed_weekdays"]
    for key in ("settings_revision", "flow_plan_revision"):
        assert attrs[key] == options[key]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-default", action="store_true")
    args = parser.parse_args()
    out = Path(os.environ["P5A_JOIN_OUTPUT"]).resolve()
    assert not out.is_relative_to(B) and not out.is_relative_to(C)
    out.mkdir(parents=True, exist_ok=True)
    run = out / "attempt1"
    producer_receipt = out / "producer-exit.json"
    if args.run_default:
        assert not run.exists() and not producer_receipt.exists()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        # The prior S5 suite writes checkout-root terminals. P5a must not do so.
        env["P3C_CAPTURE_DIR"] = str(out / "captures")
        command = [sys.executable, "-B", str(B / "tools/p5a_visual_native.py"), "attempt1"]
        with (out / "producer.log").open("wb") as log:
            child = subprocess.Popen(command, cwd=B, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                code = child.wait(timeout=420)
            except subprocess.TimeoutExpired:
                child.kill()
                code = child.wait(timeout=15)
                write(producer_receipt, {"exit_code": code, "pid": child.pid, "timeout": True})
                raise
        write(producer_receipt, {"exit_code": code, "pid": child.pid, "timeout": False})
        assert code == 0, "actual default producer failed; inspect private producer.log"
    producer = json.loads(producer_receipt.read_bytes())
    assert producer["exit_code"] == 0 and producer["timeout"] is False

    def load(name):
        return json.loads((run / name).read_bytes())

    result = load("result.json")
    assert result["exit_code"] == result["browser_exit_code"] == 0
    assert result["failure"] is None and result["smoke_only"] is False
    assert result["source_unchanged"] is True and result["child_pid"] > 0
    assert [e["case"] for e in result["events"][:-1]] == CASES
    assert result["events"] == load("events.json")
    assert result["events"][-1] == {"kind": "done", "page_errors": []}
    command = load("command.json")
    assert "--smoke" not in command["parent"]
    assert Path(command["parent"][2]).resolve() == B / "tools/p5a_visual_native.py"
    assert Path(command["child"][2]).resolve() == B / "tools/p5a_visual_browser.py"
    before, after = load("source-before.json"), load("source-after.json")
    assert before == after and load("source-guard.json") == {"unchanged": True}
    assert before[C.name + "/uninus-nutriculture-card.js"] == sha(C / (C.name + ".js")) == BUNDLE
    for relative, digest in before.items():
        path = (B.parent / relative).resolve()
        assert path.is_relative_to(B) or path.is_relative_to(C)
        assert sha(path) == digest, relative
    imports = load("actual-imports.json")
    assert (
        len(imports) == 47
        and "custom_components.uninus_nutriculture.plan_options" in imports
        and "custom_components.uninus_nutriculture.options_auth" in imports
    )
    for name, row in imports.items():
        path = Path(row["path"]).resolve()
        assert path.is_relative_to(B) and sha(path) == row["sha256"]
        source = (
            B / (name.replace(".", "/") + ".py")
            if name.startswith("custom_components.")
            else B / "tests" / (name + ".py")
        )
        if name == "custom_components.uninus_nutriculture":
            source = B / "custom_components/uninus_nutriculture/__init__.py"
        assert source.resolve() == path and sha(source) == row["sha256"], name
    wire = load("wire.json")
    assert result["native_requests"] == len(wire) == 19
    assert [w["emitted"]["service"] for w in wire] == ["preview_flow_plan_v5"] * 15 + [
        "apply_flow_plan_v5"
    ] * 4
    assert all(w["reply"]["success"] is True for w in wire[:-1])
    assert wire[-1]["reply"]["success"] is False
    assert "settings_conflict" in wire[-1]["reply"]["error"]["message"]
    assert all(w["io"] == {"refill": [], "dosing": [], "acid_on": False} for w in wire)
    assert [w["commit_count"] for w in wire] == [0] * 15 + [1, 2, 4, 4]
    for index, row in enumerate(wire):
        request = row["request"]
        assert request["id"] == index + 1 == row["reply"]["id"]
        assert {k: v for k, v in request.items() if k != "id"} == row["emitted"]
        assert request["domain"] == "uninus_nutriculture" and request["return_response"] is True
        if index < 15:
            assert row["options"] == wire[0]["options"]
        elif row["reply"]["success"]:
            payload, options = request["service_data"], row["options"]
            response = row["reply"]["result"]["response"]
            assert response["applied"] is True
            assert payload["flow_plan"] == options["flow_plan"] == response["flow_plan"]
            assert payload["allowed_weekdays"] == options["control"]["allowed_weekdays"]
            assert response["allowed_weekdays"] == payload["allowed_weekdays"]
            for key in ("settings_revision", "flow_plan_revision"):
                assert response[key] == options[key]
    assert wire[-1]["options"] == wire[-2]["options"]
    for offset in (1, 8):
        previews = wire[offset : offset + 7]
        assert [w["request"]["service_data"]["weekday"] for w in previews] == [
            "mon",
            "tue",
            "wed",
            "thu",
            "fri",
            "sat",
            "sun",
        ]
    for name in ("options-preview-cancel.json", "options-stale.json"):
        row = load(name)
        unchanged(row["before"], row["after"])
        truth(row["before"])
        truth(row["after"])
    assert load("options-stale.json")["errors"]["base"] == "settings_conflict"
    saved = load("options-save.json")
    old, new = saved["before"], saved["after"]
    expected = json.loads(json.dumps(old["options"]))
    expected["control"]["allowed_weekdays"]["acid"] = new["options"]["control"]["allowed_weekdays"][
        "acid"
    ]
    for key in ("settings_revision", "flow_plan_revision"):
        expected[key] += 1
    assert new["options"] == expected
    assert new["commit_count"] == old["commit_count"] + 1 and new["io"] == old["io"]
    truth(new)
    initial = wire[0]["options"]
    allowed = {"flow_plan", "flow_plan_revision", "settings_revision", "control"}
    assert {k: v for k, v in initial.items() if k not in allowed} == {
        k: v for k, v in wire[-1]["options"].items() if k not in allowed
    }
    assert {k: v for k, v in initial["control"].items() if k != "allowed_weekdays"} == {
        k: v for k, v in wire[-1]["options"]["control"].items() if k != "allowed_weekdays"
    }
    assert load("fresh-store-readback.json")["options"] == wire[-1]["options"]
    fresh = load("fresh-sdk-readback.json")
    assert fresh["options"] == wire[-1]["options"]
    # Windows venv launchers and their Python child have different PIDs.
    # The unchanged native helper asserts its os.getpid() differs from this readback.
    assert fresh["pid"] > 0 and load("fresh-exit.json")["pid"] > 0
    assert fresh["pid"] != result["child_pid"]
    assert load("fresh-exit.json")["exit_code"] == 0 and fresh["entry_state"] == "loaded"
    assert fresh["status"]["flow_plan"] == fresh["options"]["flow_plan"]
    assert fresh["status"]["allowed_weekdays"] == fresh["options"]["control"]["allowed_weekdays"]
    for key in ("settings_revision", "flow_plan_revision"):
        assert fresh["status"][key] == fresh["options"][key]
    messages = [json.loads(line) for line in (run / "ipc.raw.jsonl").read_bytes().splitlines()]
    replies = [
        json.loads(line) for line in (run / "ipc-replies.raw.jsonl").read_bytes().splitlines()
    ]
    assert len(messages) == len(replies) and messages[-1]["kind"] == "done"
    assert [m["id"] for m in messages] == list(range(1, len(messages) + 1))
    for message, reply in zip(messages, replies, strict=True):
        assert "harness_error" not in reply
        if message["kind"] == "inspect":
            truth(reply)
    # These completed checkpoints follow the original browser's full equality and dirty-draft assertions.
    receipt = {
        "producer_exit": producer["exit_code"],
        "browser_exit": result["browser_exit_code"],
        "fresh_sdk_exit": load("fresh-exit.json")["exit_code"],
        "default_mode": not result["smoke_only"],
        "native_requests": len(wire),
        "native_previews": 15,
        "behavior_checkpoints": len(CASES),
        "imports": len(imports),
        "bundle_sha256": BUNDLE,
        "source_unchanged": before == after,
        "Options_Preview_Cancel_Save_stale": True,
        "Store_freshload_freshSDK_equal": True,
        "full_native_Card_truth": True,
        "two_Card_dual_CAS_loser_dirty_not_rebased": True,
        "old_options_namespaces_preserved": True,
        "zero_IO": True,
        "page_errors": [],
        "sdk": command["core"],
        "browser": result["events"][0]["browser"],
        "shutdown_warning_count": sum(
            path.read_text(encoding="utf-8").count(
                "was still running after final writes shutdown stage"
            )
            for path in (out / "producer.log", run / "fresh.stderr.log")
        ),
        "scope": "isolated P5a visual/mobile-keyboard only; not publication or source approval",
    }
    # Export paths/hashes only for current code/config, never runtime, archived proof or Git metadata.
    safe_map = {
        key: value
        for key, value in before.items()
        if (
            key.startswith(B.name + "/custom_components/")
            or key.startswith(B.name + "/tests/")
            or key.startswith(B.name + "/tools/")
        )
        and Path(key).suffix in (".py", ".json", ".yaml")
        or key
        in (
            B.name + "/.github/workflows/tests.yml",
            C.name + "/.github/workflows/validate.yml",
            C.name + "/uninus-nutriculture-card.js",
            B.name + "/requirements-test.txt",
            C.name + "/requirements-test.txt",
            B.name + "/pyproject.toml",
        )
    }
    safe = out.parent / (out.name + "-safe-export")
    safe.mkdir(exist_ok=False)
    write(safe / "ci-verified.json", receipt)
    write(safe / "source-before.json", safe_map)
    write(safe / "source-after.json", {key: after[key] for key in safe_map})
    names = ["ci-verified.json", "source-before.json", "source-after.json"]
    write(
        safe / "EXPORT_MANIFEST.json",
        {
            "files": [
                {"path": name, "sha256": sha(safe / name), "bytes": (safe / name).stat().st_size}
                for name in names
            ],
            "excluded": [
                "raw DTO",
                "DOM",
                "wires",
                "Store",
                "auth",
                "capabilities",
                "runtime",
                "Git metadata",
            ],
        },
    )
    assert {p.name for p in safe.iterdir()} == set(names + ["EXPORT_MANIFEST.json"])
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
