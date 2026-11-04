"""Owned, offline round-4 snapshot and real child evidence runner."""

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "quality-round4"
FROZEN = Path("C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3c-review-r3-successor")
QUALITY = Path("C:/Users/ivanl/.hermes/cache/scratch/p3c-quality-review-1")
SDK = "D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe"
CARD_SDK = "D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(root):
    return {
        p.relative_to(root).as_posix(): sha(p)
        for folder in ("custom_components", "tests", "tools")
        for p in (root / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    } | {name: sha(root / name) for name in ("pyproject.toml", "requirements-test.txt")}


def main():
    label = sys.argv[1]
    dest = OUT / label
    dest.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((FROZEN / "MANIFEST.json").read_text())["files"]
    assert (
        sha(FROZEN / "MANIFEST.json")
        == "477bf2eb9102adeddf26cfb72b3d062ee67f83da5a71cca9711c442a173eddaf"
    )
    assert len(manifest) == 198
    assert all(sha(FROZEN / k) == h for k, h in manifest.items())
    build = dest / "build"
    backend = build / "uninus-nutriculture"
    backend.mkdir(parents=True)
    for key in manifest:
        src = (
            ROOT / key.split("/", 1)[1] if key.startswith("uninus-nutriculture/") else FROZEN / key
        )
        target = build / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    before = inputs(ROOT)
    for rel in before:
        target = backend / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    for name, expected in (
        (
            "test_quality_probe.py",
            "98ef93eab2ab8ff3473adff549e3416428db1502aa42cfc2b4a04e054dd11640",
        ),
        (
            "test_repeat_probe.py",
            "411f73296567514affe626b177ae5a17d6a0d1eca96ba1c905187dee6a36d830",
        ),
    ):
        src = QUALITY / "build/uninus-nutriculture/tests" / name
        assert sha(src) == expected
        shutil.copy2(src, backend / "tests" / name)
    shutil.copy2(
        QUALITY / "build/uninus-nutriculture/quality_imports.py", backend / "quality_imports.py"
    )
    frozen_inputs = inputs(backend)
    args = sys.argv[2:] or [
        "tests/test_quality_probe.py",
        "tests/test_repeat_probe.py",
        "tests/test_p3c_flow.py::test_v5_pending_circ_on_does_not_block_independent_safety_off",
        "tests/test_p3c_flow.py::test_two_circ_owners_first_completion_never_turns_off_other",
    ]
    cmd = [
        SDK,
        "-B",
        "-m",
        "pytest",
        "-p",
        "quality_imports",
        *args,
        "-vv",
        "--tb=short",
        "--basetemp",
        str(dest / "runtime"),
    ]
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(backend),
        P3A_CARD_PYTHON=CARD_SDK,
        P3B_CARD_PYTHON=CARD_SDK,
        CHROMIUM_EXECUTABLE="C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe",
        TMPDIR=str(dest / "temp"),
        TEMP=str(dest / "temp"),
        TMP=str(dest / "temp"),
    )
    (dest / "temp").mkdir()
    started = datetime.datetime.now(datetime.UTC).isoformat()
    with (dest / "raw.log").open("wb") as log:
        child = subprocess.Popen(
            cmd,
            cwd=backend,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            code = child.wait(timeout=420)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], check=False)
            code = -999
            child.wait()
    imports = (
        json.loads((backend / "quality-actual-imports.json").read_text())
        if (backend / "quality-actual-imports.json").exists()
        else []
    )
    bad = []
    for row in imports:
        path = Path(row["path"])
        assert path.is_relative_to(dest), row
        suffix = (
            path.relative_to(backend).as_posix()
            if path.is_relative_to(backend)
            else "custom_components/" + path.as_posix().split("/custom_components/", 1)[1]
        )
        if frozen_inputs.get(suffix) != row["sha256"] or sha(path) != row["sha256"]:
            bad.append(row)
    receipt = dict(
        label=label,
        started=started,
        ended=datetime.datetime.now(datetime.UTC).isoformat(),
        command=cmd,
        cwd=str(backend),
        environment={
            k: env[k]
            for k in ("PYTHONPATH", "P3A_CARD_PYTHON", "P3B_CARD_PYTHON", "CHROMIUM_EXECUTABLE")
        },
        child_exit=code,
        raw_sha256=sha(dest / "raw.log"),
        source_before=before,
        source_after=inputs(ROOT),
        snapshot_before=frozen_inputs,
        snapshot_after=inputs(backend),
        actual_imports=imports,
        import_mismatches=bad,
        original_manifest_unchanged=all(sha(FROZEN / k) == h for k, h in manifest.items()),
    )
    (dest / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf8")
    print((dest / "raw.log").read_text(encoding="utf8", errors="replace"))
    assert receipt["source_before"] == receipt["source_after"]
    assert receipt["snapshot_before"] == receipt["snapshot_after"]
    assert not bad
    print("CHILD_EXIT", code, "RAW_SHA256", receipt["raw_sha256"])
    return code


if __name__ == "__main__":
    sys.exit(main())
