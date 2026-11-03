"""P1 monitoring remains passive; P2 output dispatch has one explicit owner."""

import ast
from pathlib import Path


def test_output_dispatch_is_controller_only_and_no_duplicate_mqtt_client():
    folder = Path(__file__).resolve().parents[1] / "custom_components" / "uninus_nutriculture"
    for path in folder.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {
                "async_call",
                "call_service",
                "async_publish",
            }:
                assert path.name == "control.py", (path.name, node.attr)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [x.name for x in node.names] + [getattr(node, "module", "") or ""]
                assert not any("mqtt" in name.lower() for name in names)
