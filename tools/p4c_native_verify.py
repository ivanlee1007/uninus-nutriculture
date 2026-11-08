"""Strict verifier of the proven P4c native scenario; safe summary export only."""

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path

from p4c_source_inputs import source_hashes

BUNDLE = "e2b683af4bf40c16e328f8ae4108b0a0a519818cf84862b1e14ba317c49af4fe"
B = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", default=os.environ.get("P4C_JOIN_OUTPUT"))
parser.add_argument("--card-repo", default=os.environ.get("P4C_CARD_REPO"))
args = parser.parse_args()
if not args.output:
    parser.error("--output or P4C_JOIN_OUTPUT required")
R = Path(args.output).resolve()
C = Path(args.card_repo).resolve() if args.card_repo else B.parent / "uninus-nutriculture-card"


def load(name):
    return json.loads((R / name).read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert metadata.version("homeassistant") == "2026.10.4"
assert sha(C / "uninus-nutriculture-card.js") == BUNDLE
before = load("source-before.json")
assert before == load("source-after.json") == source_hashes(B, C)
result = load("result.json")
wire = load("wire.json")
assert result["raw_child_exit"] == 0
assert result["native_requests"] == len(wire) == 5
assert result["checkpoints"] == 4
assert not (R / "first-native-exception.json").exists()
assert all(w["reply"]["success"] for w in wire)
assert [w["request"]["type"].rsplit("/", 1)[1] for w in wire] == [
    "get",
    "save",
    "get",
    "get",
    "get",
]
assert all(w["io"] == {"refill": [], "dosing": [], "acid_on": False} for w in wire[:4])
assert set(load("registered-routes.json")) == {
    "uninus_nutriculture/notification_v1/" + suffix
    for suffix in ("ack", "get", "reconcile", "save")
}
store = load("physical-store.json")
assert store["zero_actuator_calls"] is True
assert store["document"]["data"] == store["fresh_store_load"]
assert store["fresh_store_load"]["revision"] == store["card_cached"]["revision"] == 1
assert store["fresh_store_load"]["policy"] == store["card_cached"]["policy"]
options = load("native-options.json")
assert options["cancel_revision_unchanged"] is True
assert options["options_unchanged"] is True
assert options["revision"] == 2
assert options["submitted"] == {
    "enabled": True,
    "provider": "persistent_notification",
    "events": ["start", "completed"],
    "cooldown_seconds": 600,
    "action": "save",
}
terminal = load("terminal-native.json")
dto = terminal["dto"]
assert terminal["native_attributes"] == dto
assert dto["current_run"] is None
assert dto["last_result"]["state"] == "completed"
assert dto["last_result"]["closure"] == "confirmed"
assert not terminal["leases"] and terminal["flow_pending"] is False
snap = terminal["status"]
attrs = snap["states"][snap["status_id"]]["attributes"]
assert len(attrs["step_runtime"]) == 4
assert all(row["result"] == "completed" for row in attrs["step_runtime"].values())
assert set(attrs["output_states"]) == {"refill", "nutrient", "acid", "circulation"}
assert all(value == "off" for value in attrs["output_states"].values())
assert [row["status"] for row in terminal["notification"]["deliveries"]] == [
    "handoff_returned",
    "handoff_returned",
]
assert terminal["notices"] and any("已受理" in row["message"] for row in terminal["notices"])
accepted = load("accepted-result.json")
assert accepted["current_run"] is not None and accepted["last_result"] is None
assert load("admission.json")["accepted"] is True
checkpoints = load("checkpoints.json")
assert [row["name"] for row in checkpoints] == [
    "firstrealwire_editor_native_GET",
    "Card_Save_automatic_GET_physical_Store",
    "four_stage_result_native_API_Card",
    "browser_done",
]
assert checkpoints[-1]["page_errors"] == []
assert checkpoints[2]["result"] == dto
assert checkpoints[2]["notification"] == terminal["notification"]
assert load("terminal.dom.json")["result"] == dto
assert load("terminal.dom.json")["cache"] == terminal["notification"]
imports = load("actual-imports.json")
assert imports and "conftest" in imports and "test_p3c_flow" in imports
for name, row in imports.items():
    path = Path(row["path"]).resolve()
    assert path.is_relative_to(B) or path.is_relative_to(R)
    assert sha(path) == row["sha256"]
    if name.startswith("custom_components.uninus_nutriculture"):
        parts = path.parts
        source = B / Path(*parts[parts.index("custom_components") :])
    else:
        source = B / "tests" / (name + ".py")
    assert source.is_file() and sha(source) == row["sha256"], name
receipt = {
    "native_requests": len(wire),
    "behavior_checkpoints": len(checkpoints),
    "child_exit": result["raw_child_exit"],
    "imports": len(imports),
    "source_inputs": len(before),
    "bundle_sha256": BUNDLE,
    "sdk": metadata.version("homeassistant"),
    "browser": checkpoints[-1]["browser"],
    "physical_Store_freshload_Card_equal": True,
    "Options_Save_reopen_Cancel": True,
    "management_zero_IO": True,
    "four_stages_completed_confirmed_empty_leases": True,
    "result_GET_native_Card_exact": True,
    "page_errors": [],
    "provider_claim": "native handoff_returned only; not delivered",
}
# No raw DTOs, storage/auth, policy capabilities, DOM or runtime directories exported.
safe = R.parent / (R.name + "-safe-export")
safe.mkdir(exist_ok=False)
(safe / "ci-verified.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
(safe / "source-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
(safe / "source-after.json").write_text(
    json.dumps(load("source-after.json"), indent=2), encoding="utf-8"
)
allowlist = ["ci-verified.json", "source-before.json", "source-after.json"]
(safe / "EXPORT_MANIFEST.json").write_text(
    json.dumps(
        {
            "files": [{"path": name, "sha256": sha(safe / name)} for name in allowlist],
            "excluded": ["runtime", ".storage", "auth", "capabilities", "raw DTO", "DOM", "pytest"],
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(json.dumps(receipt))
