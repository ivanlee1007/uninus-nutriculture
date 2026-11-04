import asyncio
import json
import subprocess
import sys
from pathlib import Path


async def test_fresh_process_native_config_entry_storage(tmp_path):
    worker = Path(__file__).with_name("restart_worker.py")
    results = []
    for mode in ("write", "read"):
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(worker), mode, str(tmp_path / "native-ha")],
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        data = json.loads(result.stdout.strip().splitlines()[-1])
        results.append(data)
    assert results[0] == results[1]
    saved = json.loads((tmp_path / "native-ha" / ".storage" / "core.config_entries").read_text())
    stored = saved["data"]["entries"][0]
    assert stored["entry_id"] == results[0]["entry_id"]
    assert stored["options"]["parameters"] == results[0]["parameters"]
    print("FRESH_PROCESS_STORAGE=" + json.dumps(results))
