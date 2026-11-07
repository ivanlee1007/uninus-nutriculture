"""Explicit P4c consumed-source preimage, never runtime/evidence discovery."""

import hashlib
from pathlib import Path


def source_hashes(backend: Path, card: Path) -> dict[str, str]:
    """Bind fixtures, product, runner, schema, dependencies and workflow."""
    paths = list((backend / "custom_components").rglob("*.py"))
    paths += list((backend / "tests").glob("*.py"))
    paths += list((backend / "custom_components").rglob("*.json"))
    paths += list((backend / "custom_components").rglob("*.yaml"))
    paths += list((backend / "tools").glob("p4c_*.py"))
    paths += [
        backend / name
        for name in (
            "requirements-test.txt",
            "pyproject.toml",
            ".github/workflows/tests.yml",
            "docs/P4C_API_SCHEMA.json",
            "tools/p4b_quality_verify.py",
        )
    ]
    paths += [
        card / name
        for name in (
            "uninus-nutriculture-card.js",
            "requirements-test.txt",
            "tests/check.py",
            "tests/p4c_browser.py",
            "docs/P4C_API_SCHEMA.json",
            ".github/workflows/validate.yml",
        )
    ]
    result = {}
    for path in sorted(set(paths)):
        owner = card if path.is_relative_to(card) else backend
        key = owner.name + "/" + path.relative_to(owner).as_posix()
        if key in result:
            raise ValueError("Colliding source key: " + key)
        result[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result
