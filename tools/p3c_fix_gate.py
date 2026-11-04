"""Round3 owned snapshots, child exit propagation and import provenance."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = Path("C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3c-integration-input")
SPEC = Path("C:/Users/ivanl/.hermes/cache/scratch/p3c-spec-review-1/probe_spec_v2.py")
SDK = "D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe"


def hashes(base):
    return {
        p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in base.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def main():
    name, *tests = sys.argv[1:]
    out = ROOT / "nativefixtures" / name
    out.mkdir(parents=True, exist_ok=False)
    build = out / "build"
    back = build / "uninus-nutriculture"
    back.mkdir(parents=True)
    for folder in ("custom_components", "tests", "tools"):
        shutil.copytree(ROOT / folder, back / folder, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "pyproject.toml", back)
    manifest = json.loads((FROZEN / "MANIFEST.json").read_text())["files"]
    for key in manifest:
        if key.startswith("uninus-nutriculture-card/"):
            dest = build / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FROZEN / key, dest)
    if tests == ["original"]:
        shutil.copyfile(SPEC, back / "tests/test_independent_spec.py")
        tests = ["tests/test_independent_spec.py"]
    plugin = back / "bindings_plugin.py"
    plugin.write_text(
        'import sys,json,hashlib\nfrom pathlib import Path\ndef pytest_sessionfinish(session, exitstatus):\n d={}\n for n,m in list(sys.modules.items()):\n  p=getattr(m,"__file__",None)\n  if p and (n.startswith("custom_components.uninus_nutriculture") or n.startswith("test_p") or n in ("p2_fixtures","p3_fixtures")):\n   d[n]={"path":p,"sha256":hashlib.sha256(Path(p).read_bytes()).hexdigest()}\n Path("../../actual-imports.json").write_text(json.dumps(d,indent=2))\n',
        encoding="utf8",
    )
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(back) + ";" + str(back / "tests"),
        P3A_CARD_PYTHON="D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe",
        P3B_CARD_PYTHON="D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe",
        CHROMIUM_EXECUTABLE="C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe",
    )
    args = [
        SDK,
        "-m",
        "pytest",
        *(tests or ["tests"]),
        "-vv",
        "-p",
        "bindings_plugin",
        "--basetemp",
        str(out / "runtime"),
    ]
    receipt = dict(
        command=args,
        cwd=str(back),
        utc=datetime.now(timezone.utc).isoformat(),
        source_before=hashes(build),
        env={
            k: env[k]
            for k in ("PYTHONPATH", "P3A_CARD_PYTHON", "P3B_CARD_PYTHON", "CHROMIUM_EXECUTABLE")
        },
    )
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2))
    with (out / "raw.log").open("w", encoding="utf8") as log:
        child = subprocess.Popen(
            args,
            cwd=back,
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
    receipt.update(
        exit_code=code,
        source_after=hashes(build),
        raw_sha256=hashlib.sha256((out / "raw.log").read_bytes()).hexdigest(),
    )
    receipt["inputs_unchanged"] = all(
        receipt["source_after"].get(k) == v for k, v in receipt["source_before"].items()
    )
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2))
    print((out / "raw.log").read_text(encoding="utf8"))
    print("CHILD_EXIT", code, "RECEIPT", out / "receipt.json")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
