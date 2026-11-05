from pathlib import Path
import hashlib,json

def source_hashes(root):
    paths=json.loads((root/'tools/p4b_quality_inputs.json').read_text())
    result={}
    for name in paths:
        p=(root.parent/name).resolve()
        if not p.is_relative_to(root.parent.resolve()): raise ValueError(name)
        result[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result
