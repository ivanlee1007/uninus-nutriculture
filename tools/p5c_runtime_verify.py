"""Verify closed P5c native evidence; export only fixed scalar/hash fields.

No producer execution, auth/storage access, or raw capture publication. Evidence is
trusted local CI output, not a signature of an arbitrary third-party JSON bundle.
"""

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

BUNDLE = "uninus-nutriculture-card/uninus-nutriculture-card.js"
FLAGS = {
    "include_start_time_state": True,
    "significant_changes_only": False,
    "minimal_response": False,
    "no_attributes": False,
}
CASES = [
    "shipping_native_S5_mount",
    "shipping_trace_native_1h",
    "shipping_trace_native_6h",
    "shipping_trace_native_24h",
    "shipping_trace_native_24h",
    "native_READ_partial",
    "native_READ_none",
    "native_runtime_trace_browser_complete",
]
OWNERS = {
    "read_only_effects",
    "core.async_stop",
    "child.wait",
    "child.stdout.drain",
    "child.stderr.drain",
    "dosing_fixture.aclose",
    "base_fixture.aclose",
}
FIXTURES = {
    "conftest",
    "p2_fixtures",
    "p3_fixtures",
    "test_p2_control",
    "test_p3_dosing",
    "test_p3c_flow",
}
HANDLER = "5b3fdf3acfa0c8e254819473e24408a9d54d3b0cedb8cda6f13551b5bf8ed7c0"


def require(condition, label):
    """Avoid assert so python -O cannot disable verification."""
    if not condition:
        raise ValueError(label)


def digest(path):
    require(path.is_file() and not path.is_symlink(), "missing/nonregular input")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def relative_path(name):
    rel = PurePosixPath(name)
    require(
        isinstance(name, str)
        and "\\" not in name
        and ":" not in name
        and rel.as_posix() == name
        and not rel.is_absolute()
        and ".." not in rel.parts
        and len(rel.parts) > 1
        and rel.parts[0] in ("uninus-nutriculture", "uninus-nutriculture-card"),
        "unsafe source key",
    )
    return rel


def inventory(pair):
    return {
        p.relative_to(pair).as_posix(): digest(p)
        for repo in ("uninus-nutriculture", "uninus-nutriculture-card")
        for p in (pair / repo).rglob("*")
        if p.is_file()
    }


def verify(out, candidate, expected_js_sha):
    """Return a new fixed allowlist, never a projection of private JSON objects."""
    out, candidate = Path(out).resolve(), Path(candidate).resolve()
    require(re.fullmatch(r"[0-9a-f]{64}", expected_js_sha) is not None, "expected JS hash")
    require(
        not out.is_relative_to(candidate) and not candidate.is_relative_to(out),
        "evidence/source overlap",
    )

    def read(name):
        return load(out / name)

    result = read("result.json")
    require(
        type(result["exit_code"]) is int
        and result["exit_code"] == 0
        and type(result["browser_exit_code"]) is int
        and result["browser_exit_code"] == 0
        and result["failure"] is None
        and result["fault"] is None
        and result["wire_only"] is False
        and result["verdict"] == "NATIVE_UI_ACCEPTED",
        "producer/browser incomplete or failed",
    )
    require(
        result["core_state"] == "STOPPED"
        and result["core_STOPPED"] is True
        and result["recorder_thread_alive"] is False
        and result["source_unchanged"] is True,
        "unclosed or changed source",
    )
    cleanup = result["cleanup"]
    require(
        len(cleanup) == len(OWNERS)
        and {r["owner"] for r in cleanup} == OWNERS
        and all(r == {"owner": r["owner"], "ok": True} for r in cleanup),
        "owner cleanup incomplete",
    )
    checkpoint = read("CHECKPOINT.json")
    require(checkpoint == {"state": "finished", **result}, "checkpoint not closed")
    events = read("events.json")
    require(events == result["events"], "events mismatch")
    require([e["case"] for e in events] == CASES, "eight checkpoints incomplete")
    require(
        [e["kind"] for e in events] == ["checkpoint"] * 7 + ["done"]
        and events[0]["optional_quality_result_strict_native_valid"] is True
        and isinstance(events[0]["browser"], str)
        and re.fullmatch(r"[0-9.]+", events[0]["browser"]) is not None,
        "browser completion invalid",
    )
    require([e["request_id"] for e in events[1:7]] == list(range(11, 17)), "UI wire IDs")
    ipc = [
        json.loads(line)
        for line in (out / "ipc.raw.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    require(
        [
            {"kind": row["kind"], **row["payload"]}
            for row in ipc
            if row["kind"] in ("checkpoint", "done")
        ]
        == events,
        "browser IPC checkpoints mismatch",
    )
    require(
        set(row["kind"] for row in ipc) <= {"snapshot", "ws", "inspect", "checkpoint", "done"},
        "unexpected browser IPC",
    )
    require(sum(row["kind"] == "ws" for row in ipc) == 7, "browser History requests")
    for event in events[1:5]:
        text = event["rendered_trace"]
        require(
            isinstance(text, str)
            and re.search(r"\bon\b", text) is not None
            and re.search(r"\boff\b", text) is not None
            and re.search(r"nutrient|加養", text) is not None
            and re.search(r"品質|quality", text, re.IGNORECASE) is not None
            and "HISTORICAL ONLY" in text
            and "+08:00" in text
            and "stopped" in text
            and "revoked" in text,
            "native timeline display incomplete",
        )
    require(
        re.search(r"\bon\b", events[5]["trace_list"]) is not None
        and re.search(r"\boff\b", events[5]["trace_list"]) is not None,
        "partial display missing status",
    )
    require(
        re.search(r"\b(on|off|running|aborted|stopped)\b", events[6]["trace_list"]) is None
        and re.search(r"無.*(資料|歷史)|no.*(readable|history)", events[6]["status"], re.IGNORECASE)
        is not None,
        "unreadable display leaked cached truth",
    )
    zero = read("zero-mutations.json")
    require(
        all(
            type(zero[k]) is int
            for k in ("options_commits", "feature_mutations", "browser_actuator_calls")
        )
        and zero["options_unchanged"] is True,
        "mutation counter types",
    )
    require(
        zero
        == {
            "options_unchanged": True,
            "options_commits": 0,
            "service_calls": [],
            "feature_mutations": 0,
            "browser_actuator_calls": 0,
        },
        "browser mutations",
    )
    command = read("command.json")
    original = Path(command["source_pair"]).resolve()
    require(command["versions"]["homeassistant"] == "2026.10.4", "Core pin")
    child = read("child.json")
    require(
        type(child["pid"]) is int
        and child["pid"] > 0
        and len(child["command"]) == 3
        and child["command"][1] == "-B"
        and Path(child["command"][2]).resolve()
        == original / "uninus-nutriculture-card/tests/p5c_runtime_native_browser.py",
        "explicit browser child",
    )
    before, after = read("source-before.json"), read("source-after.json")
    require(before and before == after, "source receipts changed")
    for name, sha in before.items():
        relative_path(name)
        require(re.fullmatch(r"[0-9a-f]{64}", sha) is not None, "source digest")
        require(digest(out / "source-bytes" / name) == sha, "captured source mismatch")
    require(inventory(candidate) == before, "candidate source differs from run")
    require(before[BUNDLE] == expected_js_sha, "unapproved bundle")
    imports = read("actual-imports.json")
    require(
        len(imports) == 42
        and FIXTURES <= imports.keys()
        and "custom_components.uninus_nutriculture.options_auth" in imports,
        "import receipt incomplete",
    )
    for name, row in imports.items():
        if name in FIXTURES:
            rel = "uninus-nutriculture/tests/" + name + ".py"
        else:
            require(name.startswith("custom_components.uninus_nutriculture"), "foreign import")
            base = "uninus-nutriculture/" + name.replace(".", "/")
            rel = base + ".py" if base + ".py" in before else base + "/__init__.py"
        require(
            row["canonical_bytes_equal"] is True
            and Path(row["canonical_path"]).resolve() == original / rel
            and Path(row["path"]).resolve() == original / rel
            and row["sha256"] == before[rel]
            and digest(Path(row["path"])) == before[rel]
            and digest(candidate / rel) == before[rel],
            "import/bundle provenance",
        )
    entries = read("entries.json")
    require(len(entries) == 1, "native entry count")
    mapping = entries[0]["source_entities"]
    require(set(mapping) == {"status", "quality", "result"}, "source mapping")
    sources = [mapping[k] for k in ("status", "quality", "result")]
    require(len(set(sources)) == 3, "distinct native sources")
    status, quality, terminal = sources
    wire = read("wire.json")
    require(result["wire_requests"] == len(wire) == 17, "17 native requests required")
    browser_ws = [row["payload"] for row in ipc if row["kind"] == "ws"]
    require(
        all(
            sent["message"] == received["emitted"]
            and sent["principal_id"] == received["principal_id"]
            for sent, received in zip(browser_ws, wire[10:], strict=True)
        ),
        "browser/native request equality",
    )
    principals = {}
    hours_list = [1, 1, 1, 6, 6, 6, 24, 24, 24, 24, 1, 6, 24, 24, 1, 1, 1]
    modes = ["all", "partial", "none"] * 3 + ["all"] * 5 + ["partial", "none", "all"]
    missing = "sensor.p5c_never_recorded_optional"
    for index, (row, hours, mode) in enumerate(zip(wire, hours_list, modes, strict=True), 1):
        request, reply = row["request"], row["reply"]
        require(type(request["id"]) is int and request["id"] == index, "request ID")
        require(
            reply["id"] == index and reply["type"] == "result" and reply["success"] is True,
            "native reply",
        )
        require(reply == read(f"wire-{index:04d}.raw.json"), "raw reply mismatch")
        require(
            row["emitted"] == {k: v for k, v in request.items() if k != "id"},
            "emitted query changed",
        )
        require(
            set(request) == {"id", "type", "entity_ids", "start_time", "end_time", *FLAGS},
            "query fields",
        )
        require(request["type"] == "history/history_during_period", "registered History only")
        require(all(request[k] is v for k, v in FLAGS.items()), "actual History flags")
        start, end = (datetime.fromisoformat(request[k]) for k in ("start_time", "end_time"))
        require(
            start.tzinfo is not None
            and end.tzinfo is not None
            and (end - start).total_seconds() == hours * 3600,
            "actual History window",
        )
        expected_ids = [missing] if index == 10 else [status] if index == 17 else sources
        require(request["entity_ids"] == expected_ids, "explicit native source set")
        principal = row["principal_id"]
        require(isinstance(principal, str) and principal, "native principal")
        principals.setdefault(mode, principal)
        require(principals[mode] == principal, "principal continuity")
        expected_keys = (
            set()
            if mode == "none" or index == 10
            else {status}
            if mode == "partial" or index == 17
            else set(sources)
        )
        require(set(reply["result"]) == expected_keys, "READ/missing source semantics")
        for source, rows in reply["result"].items():
            require(isinstance(rows, list) and 0 < len(rows) <= 10000, "native rows bounded")
            for sample in rows:
                require(
                    {"s", "a", "lu"} <= sample.keys()
                    and set(sample) <= {"s", "a", "lu", "lc"}
                    and isinstance(sample["a"], dict)
                    and type(sample["lu"]) in (int, float)
                    and math.isfinite(sample["lu"])
                    and sample["lu"] > 1e9,
                    "compressed native row",
                )
    require(len(set(principals.values())) == 3, "distinct READ principals")
    proof = read("wire-proof.json")
    require(
        proof["core"] == "2026.10.4"
        and proof["flags"] == FLAGS
        and proof["registered_handler_sha256"] == HANDLER,
        "native handler receipt",
    )
    require(digest(Path(proof["registered_handler_file"])) == HANDLER, "native handler bytes")
    expected_proof = [
        {
            "hours": hours_list[i],
            "principal": modes[i],
            "sources": list(wire[i]["reply"]["result"]),
            "request_id": i + 1,
        }
        for i in range(9)
    ] + [{"principal": "all", "missing_entity": missing, "request_id": 10, "result": {}}]
    require(proof["proof"] == expected_proof, "native proof/wire disagreement")
    counts = dict(proof["sqlite_readback_counts"])
    require(all(type(counts[s]) is int and counts[s] >= 3 for s in sources), "Recorder ingestion")
    seeded = read("seeded-native-states.json")
    require({row["source"] for row in seeded} == set(sources), "native source samples incomplete")
    for i in (0, 3, 6, 10, 11, 12, 13):
        native = wire[i]["reply"]["result"]
        for source in sources:
            for sample in (s for s in seeded if s["source"] == source):
                require(
                    any(
                        r["s"] == sample["state"] and r["a"] == sample["attributes"]
                        for r in native[source]
                    ),
                    "Recorder/native sample equality",
                )
        outputs = [r["a"].get("output_states", {}).get("nutrient") for r in native[status]]
        require("on" in outputs and "off" in outputs, "native status ON/OFF")
        require(
            any(
                r["a"].get("last_result", {}).get("reason") == "revoked"
                for r in native[terminal]
                if isinstance(r["a"].get("last_result"), dict)
            ),
            "native terminal reason",
        )
    for event in events[1:5]:
        require(
            event["native_last_result"]["state"] == "stopped"
            and event["native_last_result"]["closure"] == "confirmed"
            and event["native_last_result"]["reason"] == "revoked",
            "UI/native terminal result",
        )
        require(
            any(
                r["a"].get("last_result") == event["native_last_result"]
                for r in wire[event["request_id"] - 1]["reply"]["result"][terminal]
            ),
            "UI/native result equality",
        )
    # New values only: private strings/paths/identities never cross this boundary.
    return {
        "schema": 1,
        "verdict": "NATIVE_UI_ACCEPTED",
        "core_version": "2026.10.4",
        "producer_exit_code": 0,
        "browser_exit_code": 0,
        "native_requests": 17,
        "browser_checkpoints": 8,
        "imported_modules": len(imports),
        "source_files": len(before),
        "source_manifest_sha256": hashlib.sha256(
            json.dumps(before, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "shipped_sha256": expected_js_sha,
        "result_sha256": digest(out / "result.json"),
        "wire_sha256": digest(out / "wire.json"),
        "imports_sha256": digest(out / "actual-imports.json"),
        "core_stopped": True,
        "recorder_stopped": True,
        "all_owners_closed": True,
        "source_unchanged": True,
        "zero_browser_mutations": True,
        "read_filter_and_missing_verified": True,
        "physical_acceptance": False,
        "http_bearer_handshake_exercised": False,
        "retention_span_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--expected-js-sha", required=True)
    parser.add_argument("--safe-export", required=True)
    args = parser.parse_args()
    target = Path(args.safe_export).resolve()
    try:
        require(not target.exists(), "safe export must be absent")
        for root in (Path(args.out).resolve(), Path(args.candidate).resolve()):
            require(
                not target.is_relative_to(root) and not root.is_relative_to(target.parent),
                "unsafe export destination",
            )
        summary = verify(args.out, args.candidate, args.expected_js_sha)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, sort_keys=True, indent=2)
            stream.write("\n")
        print(json.dumps(summary, sort_keys=True))
        return 0
    except ValueError, KeyError, TypeError, OSError, IndexError:
        # No private exception values/paths or captured browser payloads in CI log.
        print(
            "P5C_VERIFY_REFUSED: invalid, incomplete, changed, or unsafe evidence", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
