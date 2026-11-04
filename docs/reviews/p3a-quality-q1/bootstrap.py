"""Create owned review harness only; never touch sealed inputs."""
from pathlib import Path
import hashlib
OUT=Path(__file__).parent
SPEC=OUT.parent/'p3a-spec-q1-recheck'
src=(SPEC/'run_recheck.py').read_bytes()
(OUT/'run_recheck_spec_original.py').write_bytes(src)
text=src.decode().replace("[QUALITY,REPAIR,SCR/'p3a-spec-f1-recheck']", "[QUALITY,REPAIR,SCR/'p3a-spec-f1-recheck',SCR/'p3a-spec-q1-recheck']")
text=text.replace('# Q1 SPEC recheck in progress','# Q1 QUALITY recheck in progress')
(OUT/'run_recheck.py').write_bytes(text.encode())
print('created owned runner; original sha',hashlib.sha256(src).hexdigest())
