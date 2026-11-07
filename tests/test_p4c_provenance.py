import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path


def test_sdk_and_working_source_provenance():
    import homeassistant

    import custom_components.uninus_nutriculture.notifications as notifications
    import custom_components.uninus_nutriculture.results as results

    root = Path(__file__).resolve().parents[1]
    assert Path(results.__file__).resolve().is_relative_to(root)
    assert Path(notifications.__file__).resolve().is_relative_to(root)
    data = {
        "python": sys.version,
        "executable": sys.executable,
        "core": importlib.metadata.version("homeassistant"),
        "sdk_file": homeassistant.__file__,
        "modules": {
            m.__name__: {
                "file": m.__file__,
                "sha256": hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),
            }
            for m in (results, notifications)
        },
    }
    if os.environ.get("P4C_PROVENANCE"):
        Path(os.environ["P4C_PROVENANCE"]).write_text(json.dumps(data, indent=2))
    assert data["core"] == "2026.10.4"
