"""Owned immutable per-run SDK build; never consumes an in-flight Card tree."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEER = Path(
    "C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3b-review-q-successor/uninus-nutriculture-card"
)
SDK = "D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe"


def hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and ".venv" not in p.parts
        and ".git" not in p.parts
    }


def main():
    name = sys.argv[1]
    out = ROOT / "nativefixtures" / name
    out.mkdir(parents=True, exist_ok=False)
    build = out / "build"
    backend = build / "uninus-nutriculture"
    backend.mkdir(parents=True)
    for directory in ("custom_components", "tests", "tools"):
        shutil.copytree(
            ROOT / directory, backend / directory, ignore=shutil.ignore_patterns("__pycache__")
        )
    shutil.copy2(ROOT / "pyproject.toml", backend)
    shutil.copytree(
        PEER,
        build / "uninus-nutriculture-card",
        ignore=shutil.ignore_patterns("__pycache__", ".git", ".venv", "node_modules"),
    )
    before = hashes(build)
    env = dict(os.environ)
    env["P3B_CARD_PYTHON"] = (
        "D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe"
    )
    env["P3A_CARD_PYTHON"] = env["P3B_CARD_PYTHON"]
    env["CHROMIUM_EXECUTABLE"] = (
        "C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe"
    )
    args = [
        SDK,
        "-m",
        "pytest",
        *(sys.argv[2:] or ["tests/test_p3c_flow.py"]),
        "-vv",
        "--basetemp",
        str(out / "runtime"),
    ]
    metadata = {
        "command": args,
        "cwd": str(backend),
        "utc": datetime.now(timezone.utc).isoformat(),
        "source_before": before,
        "peer_binding": str(PEER),
        "sdk": SDK,
        "env_bindings": {
            k: env[k] for k in ("P3A_CARD_PYTHON", "P3B_CARD_PYTHON", "CHROMIUM_EXECUTABLE")
        },
    }
    (out / "receipt.json").write_text(json.dumps(metadata, indent=2), encoding="utf8")
    with (out / "raw.log").open("w", encoding="utf8") as log:
        child = subprocess.Popen(
            args,
            cwd=backend,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            code = child.wait(timeout=480)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], check=False)
            code = 124
    metadata.update(exit_code=code, source_after=hashes(build))
    # Runtime HA copies may be created under build by individual legacy probes;
    # hashes of consumed inputs above are retained independently.
    metadata["input_bytes_unchanged"] = all(
        metadata["source_after"].get(k) == v for k, v in before.items()
    )
    (out / "receipt.json").write_text(json.dumps(metadata, indent=2), encoding="utf8")
    print((out / "raw.log").read_text(encoding="utf8"))
    print("RECEIPT", out / "receipt.json", "CHILD_EXIT", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
