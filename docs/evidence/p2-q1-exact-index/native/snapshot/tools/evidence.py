"""Capture exact pre-run sources/tests and unmodified test output."""

import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
label = sys.argv[1]
dest = root / "docs" / "evidence" / label
dest.mkdir(parents=True, exist_ok=False)
hashes = {}
for folder in ("custom_components", "tests"):
    for path in (root / folder).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            rel = path.relative_to(root)
            raw = path.read_bytes()
            target = dest / "snapshot" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            hashes[str(rel)] = hashlib.sha256(raw).hexdigest()
for filename in ("pyproject.toml", "requirements-test.txt", "tools/evidence.py"):
    raw = (root / filename).read_bytes()
    target = dest / "snapshot" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    hashes[filename] = hashlib.sha256(raw).hexdigest()
env = dict(os.environ)
extra = []
if os.name == "nt":
    scratch = Path.home() / ".hermes" / "cache" / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    env.update(TMPDIR=str(scratch), TEMP=str(scratch), TMP=str(scratch))
    if "--basetemp" not in sys.argv:
        extra = ["--basetemp", str(scratch / ("nutriculture-" + label))]
cmd = [sys.executable, "-m", "pytest", *sys.argv[2:], *extra]
r = subprocess.run(
    cmd,
    check=False,
    cwd=root,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    timeout=180,
)
(dest / "pytest.log").write_bytes(r.stdout)
(dest / "run.json").write_text(
    json.dumps(
        {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "command": cmd,
            "returncode": r.returncode,
            "sha256": hashes,
        },
        indent=2,
    )
)
print(r.stdout.decode(errors="replace"))
sys.exit(r.returncode)
