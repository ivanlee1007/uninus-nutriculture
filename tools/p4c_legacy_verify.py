"""Retain every P4b verifier assertion with the current approved Card binding.

The historical verifier remains byte-identical. Only its old shipped-bundle
checksum literal is rebound at execution; this is adaptation, not byte equality.
"""

import ast
import hashlib
from pathlib import Path

B = Path(__file__).resolve().parents[1]
path = B / "tools/p4b_quality_verify.py"
raw = path.read_bytes()
assert (
    hashlib.sha256(raw).hexdigest()
    == "2e1e4c29462e76db28c476c91fe529b34805ea5b462e3bce3ae2cafb1f0db5e9"
)
old = "85304603e7870baa1d31ac27f74f11b206d1a0cac24bfe281c8a1bf308c41798"
new = "b8db3cfd204222f5226be1c3b05ff35355bac7a64bf284983d1f2bc22781a359"
text = raw.decode("utf-8")
assert text.count(old) == 1
adapted = text.replace(old, new)
# No assertion/control-flow change beyond the explicit bundle identity literal.
assert ast.dump(ast.parse(adapted.replace(new, old))) == ast.dump(ast.parse(text))
exec(compile(adapted, str(path), "exec"), {"__file__": str(path), "__name__": "__main__"})
