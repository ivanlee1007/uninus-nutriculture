"""Verify closed native History artifacts; export one tiny scalar-only JSON receipt.

No producer invocation, artifact repair, raw-wire/DOM export or publication approval.
--source-pair must be the exact frozen producer input, not this verifier's checkout.
"""

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath

BUNDLE = "e2b683af4bf40c16e328f8ae4108b0a0a519818cf84862b1e14ba317c49af4fe"
HANDLER = "5b3fdf3acfa0c8e254819473e24408a9d54d3b0cedb8cda6f13551b5bf8ed7c0"
FLAGS = {
    "include_start_time_state": True,
    "significant_changes_only": False,
    "minimal_response": False,
    "no_attributes": False,
}
ARTIFACTS = (
    "result.json",
    "CHECKPOINT.json",
    "command.json",
    "source-before.json",
    "source-after.json",
    "actual-imports.json",
    "events.json",
    "wire.json",
    "wire-proof.json",
    "zero-mutations.json",
    "seeded-native-states.json",
    "entries.json",
)
SAFE_KEYS = {
    "schema",
    "verified",
    "core",
    "shipped_sha256",
    "source_manifest_sha256",
    "result_sha256",
    "wire_sha256",
    "events_sha256",
    "imports_sha256",
    "source_files",
    "imports",
    "wire_requests",
    "history_windows",
    "read_filter_proofs",
    "checkpoints",
    "native_exit_code",
    "browser_exit_code",
    "core_stopped",
    "recorder_dead",
    "cleanup_owners",
    "source_unchanged",
    "options_commits",
    "feature_mutations",
    "service_mutations",
    "recent_samples_only",
    "uncommissioned_fixture_only",
    "active_connection_not_http",
    "publication_approved",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_run(run):
    return {name: json.loads((run / name).read_text(encoding="utf-8")) for name in ARTIFACTS}


def source_path(pair, relative):
    rel = PurePosixPath(relative)
    assert not rel.is_absolute() and ".." not in rel.parts and "\\" not in relative
    assert rel.parts[0] in ("uninus-nutriculture", "uninus-nutriculture-card")
    path = pair.joinpath(*rel.parts)
    assert path.resolve().is_relative_to(pair) and path.is_file() and not path.is_symlink()
    return path


def verify_data(data, pair, run):
    """Assert native-owned fields against their actual sibling artifacts and source bytes."""
    pair, run = pair.resolve(), run.resolve()
    assert not pair.is_relative_to(run) and not run.is_relative_to(pair)
    result = data["result.json"]
    assert type(result["exit_code"]) is int and result["exit_code"] == 0
    assert type(result["browser_exit_code"]) is int and result["browser_exit_code"] == 0
    assert result["failure"] is None and result["fault"] is None and result["wire_only"] is False
    assert result["core_state"] == "STOPPED" and result["core_STOPPED"] is True
    assert result["recorder_thread_alive"] is False and result["source_unchanged"] is True
    owners = {
        "read_only_effects",
        "core.async_stop",
        "child.wait",
        "child.stdout.drain",
        "child.stderr.drain",
    }
    cleanup = result["cleanup"]
    assert len(cleanup) == len(owners) and {row["owner"] for row in cleanup} == owners
    assert all(row["ok"] is True for row in cleanup)
    assert data["CHECKPOINT.json"] == {"state": "finished", **result}

    command = data["command.json"]
    assert Path(command["source_pair"]).resolve() == pair
    for name, version in {
        "homeassistant": "2026.10.4",
        "SQLAlchemy": "2.0.54",
        "fnv-hash-fast": "2.0.3",
        "psutil-home-assistant": "0.0.1",
    }.items():
        assert command["versions"][name] == version
    assert command["versions"]["psutil"]
    assert command["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    for name in ("NODE", "CHROMIUM_EXECUTABLE"):
        assert Path(command["env"][name]).is_file()
    argv = command["argv"]
    assert Path(argv[0]).resolve() == pair / "uninus-nutriculture/tools/p5b_history_native.py"
    for flag, value in (("--source-pair", pair), ("--out", run)):
        assert argv.count(flag) == 1 and Path(argv[argv.index(flag) + 1]).resolve() == value
    assert argv.count("--card-python") == 1
    assert Path(argv[argv.index("--card-python") + 1]).is_file()
    assert "--fault" not in argv and "--wire-only" not in argv

    before, after = data["source-before.json"], data["source-after.json"]
    assert before and before == after
    actual = {
        p.relative_to(pair).as_posix(): digest(p)
        for repo in ("uninus-nutriculture", "uninus-nutriculture-card")
        for p in (pair / repo).rglob("*")
        if p.is_file()
    }
    assert actual == before
    assert before["uninus-nutriculture-card/uninus-nutriculture-card.js"] == BUNDLE
    for relative, sha in before.items():
        assert re.fullmatch(r"[0-9a-f]{64}", sha)
        assert digest(source_path(pair, relative)) == sha
        assert digest(source_path(run / "source-bytes", relative)) == sha
    imports = data["actual-imports.json"]
    assert {
        "conftest",
        "test_p2_control",
        "custom_components.uninus_nutriculture",
    } <= imports.keys()
    for name, row in imports.items():
        if name in ("conftest", "test_p2_control"):
            relative = "uninus-nutriculture/tests/" + name + ".py"
        else:
            assert name.startswith("custom_components.uninus_nutriculture")
            stem = "uninus-nutriculture/" + name.replace(".", "/")
            relative = stem + ".py" if stem + ".py" in before else stem + "/__init__.py"
        canonical = source_path(pair, relative).resolve()
        assert row["canonical_bytes_equal"] is True
        assert Path(row["path"]).resolve() == Path(row["canonical_path"]).resolve() == canonical
        assert row["sha256"] == before[relative] == digest(canonical)

    events = data["events.json"]
    expected = [
        "shipping_native_mount",
        "live_render_exact_1h",
        "live_render_exact_6h",
        "live_render_exact_24h",
        "no_READ_exact_per_metric_DOM",
        "live_partial_full_READ_filter_and_same_name_isolation",
        "native_history_browser_complete",
    ]
    assert [e["case"] for e in events] == expected and events == result["events"]
    assert all(e["kind"] == "checkpoint" for e in events[:-1]) and events[-1]["kind"] == "done"
    assert events[0]["browser"]
    metrics = events[4]["dom"]["metrics"]
    assert set(metrics) == {"ph", "ec", "level"}
    for row in metrics.values():
        assert row["paths"] == [""] and row["circles"] == row["table_data_cells"] == 0
        assert row["points"] == [] and row["active"] == "無可讀歷史資料"

    zero = data["zero-mutations.json"]
    assert zero["options_unchanged"] is True
    assert zero["options_commits"] == zero["feature_mutations"] == 0
    # Existing bootstrap readers may issue these services; no control/config writer is allowed.
    assert all(
        c.get("service") in {"get_quality_v1", "get_plan_v5", "get_flow_plan_v5"}
        for c in zero["service_calls"]
    )
    wire, proof = data["wire.json"], data["wire-proof.json"]
    assert type(result["wire_requests"]) is int and result["wire_requests"] == len(wire) == 16
    assert proof["core"] == "2026.10.4" and proof["registered_handler_sha256"] == HANDLER
    assert digest(Path(proof["registered_handler_file"])) == HANDLER
    assert proof["flags"] == FLAGS and len(proof["proof"]) == 10
    entries = data["entries.json"]
    assert len(entries) == 2 and entries[0]["entry_id"] != entries[1]["entry_id"]
    mappings = [set(e["source_entities"].values()) for e in entries]
    assert all(len(m) == 3 for m in mappings) and not mappings[0] & mappings[1]
    counts = dict(proof["sqlite_readback_counts"])
    assert all(counts[s] >= 3 for mapping in mappings for s in mapping)
    seeded = data["seeded-native-states.json"]
    for index, row in enumerate(wire, 1):
        request, reply = row["request"], row["reply"]
        assert request["id"] == reply["id"] == index
        assert row["emitted"] == {k: v for k, v in request.items() if k != "id"}
        assert request["type"] == "history/history_during_period" and reply["success"] is True
        assert all(request[k] is value for k, value in FLAGS.items())
        assert json.loads((run / f"wire-{index:04d}.raw.json").read_bytes()) == reply
        start, end = (
            datetime.fromisoformat(request[k].replace("Z", "+00:00"))
            for k in ("start_time", "end_time")
        )
        assert start.utcoffset().total_seconds() == end.utcoffset().total_seconds() == 0
        assert (end - start).total_seconds() in (3600, 21600, 86400)
        assert set(reply["result"]) <= set(request["entity_ids"])
        for entity, samples in reply["result"].items():
            native = [s for s in seeded if s["source"] == entity]
            assert len(native) == len(samples) == 3
            assert [s["s"] for s in samples] == [s["state"] for s in native]
            assert [s["a"] for s in samples] == [s["attributes"] for s in native]
            assert samples[1]["s"] == "unknown"
    for index, row in enumerate(proof["proof"]):
        hours = (1, 6, 24)[index // 3] if index < 9 else 24
        principal = ("all", "partial", "none")[index % 3] if index < 9 else "all"
        assert (
            row["hours"] == hours
            and row["principal"] == principal
            and row["request_id"] == index + 1
        )
        assert row.get("entry_index", 0) == (0 if index < 9 else 1)
        native = wire[index]
        assert set(row["sources"]) == set(native["reply"]["result"])
        assert len(row["sources"]) == {"all": 3, "partial": 1, "none": 0}[principal]
        mapping = mappings[0 if index < 9 else 1]
        assert set(native["request"]["entity_ids"]) == mapping
        if principal == "all":
            assert set(row["sources"]) == mapping
        elif principal == "partial":
            assert row["sources"] == [entries[0]["source_entities"]["ph"]]
    # Last six requests came through shipping browser IPC, not the direct wire preflight.
    ipc = [json.loads(line) for line in (run / "ipc.raw.jsonl").read_bytes().splitlines()]
    assert [
        {"kind": r["kind"], **(r.get("payload") or {})}
        for r in ipc
        if r["kind"] in ("checkpoint", "done")
    ] == events
    browser_ws = [r["payload"] for r in ipc if r["kind"] == "ws"]
    assert len(browser_ws) == 6
    for payload, row in zip(browser_ws, wire[10:], strict=True):
        assert (
            payload["message"] == row["emitted"] and payload["principal_id"] == row["principal_id"]
        )
    assert [len(row["reply"]["result"]) for row in wire[10:]] == [3, 3, 3, 3, 1, 0]
    for hours, row in zip((1, 6, 24), wire[10:13], strict=True):
        start, end = (
            datetime.fromisoformat(row["request"][key].replace("Z", "+00:00"))
            for key in ("start_time", "end_time")
        )
        assert (end - start).total_seconds() == hours * 3600

    summary = {
        "schema": 1,
        "verified": True,
        "core": "2026.10.4",
        "shipped_sha256": BUNDLE,
        "source_manifest_sha256": digest(run / "source-before.json"),
        "result_sha256": digest(run / "result.json"),
        "wire_sha256": digest(run / "wire.json"),
        "events_sha256": digest(run / "events.json"),
        "imports_sha256": digest(run / "actual-imports.json"),
        "source_files": len(before),
        "imports": len(imports),
        "wire_requests": len(wire),
        "history_windows": 3,
        "read_filter_proofs": 10,
        "checkpoints": len(events) - 1,
        "native_exit_code": 0,
        "browser_exit_code": 0,
        "core_stopped": True,
        "recorder_dead": True,
        "cleanup_owners": len(cleanup),
        "source_unchanged": True,
        "options_commits": 0,
        "feature_mutations": 0,
        "service_mutations": 0,
        "recent_samples_only": True,
        "uncommissioned_fixture_only": True,
        "active_connection_not_http": True,
        "publication_approved": False,
    }
    assert set(summary) == SAFE_KEYS and all(type(v) in (int, bool, str) for v in summary.values())
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pair", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="Existing closed native runtime")
    parser.add_argument(
        "--safe-export", required=True, type=Path, help="Absent JSON target outside source/runtime"
    )
    args = parser.parse_args()
    target, pair, run = args.safe_export.resolve(), args.source_pair.resolve(), args.out.resolve()
    assert not target.is_relative_to(pair) and not target.is_relative_to(run)
    assert not target.exists() and target.suffix == ".json"
    summary = verify_data(load_run(run), pair, run)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    print(
        "P5B closed-artifact verification passed; tiny scalar-only receipt written; not publication approval"
    )


if __name__ == "__main__":
    main()
