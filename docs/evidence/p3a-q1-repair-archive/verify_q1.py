import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path('D:/UNiNUS Projects/AI project/uninus-nutriculture')
OUT=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((OUT/'baseline.json').read_text())
changed={p:{'before':h,'after':sha(Path(p))} for p,h in base.items() if sha(Path(p))!=h}
expected={str(ROOT/'custom_components/uninus_nutriculture'/n) for n in ('sensor.py','nutrient.py')}
assert {str(Path(p)) for p in changed}==expected,changed
receipts={}
for p in OUT.glob('*-receipt.json'):
 d=json.loads(p.read_text());name=p.name.removesuffix('-receipt.json')
 assert d['source_equal'] and d['source_before']==d['source_after']
 assert d['raw_log_sha256']==sha(OUT/(name+'.log'))
 assert d['child_exit']==(1 if name in ('red','probe-red','capture-red') else 0)
 receipts[name]={'exit':d['child_exit'],'log_sha256':d['raw_log_sha256'],'inputs':len(d['source_before'])}
for name in ('full-final','bridge-postrun-final'):
 d=json.loads((OUT/(name+'-receipt.json')).read_text())
 assert all(sha(Path(p))==h for p,h in d['source_after'].items())
for name in ('test_quality_adjacent.py','check_native_capture_ui.py','run_gate.py'):
 assert sha(OUT/name)==sha(OUT.parent/'p3a-quality-review-20261103'/name)
for label in ('red','green','full','bridge-postrun','probe-red','probe-green','full-final','bridge-postrun-final'):
 evidence=ROOT/'docs/evidence'/('p3a-q1-'+label)
 d=json.loads((evidence/'run.json').read_text())
 for rel,h in d['sha256'].items():assert sha(evidence/'snapshot'/rel)==h,(label,rel)
 assert d['returncode']==(1 if label in ('red','probe-red') else 0)
final_paths=[ROOT/'custom_components/uninus_nutriculture'/n for n in ('control.py','nutrient.py','sensor.py')]+[ROOT/'tests/test_p3_stage_projection.py',ROOT/'tools/p3a_postrun_check.py',ROOT.parent/'uninus-nutriculture-card/uninus-nutriculture-card.js']
final={str(p):sha(p) for p in final_paths}
# Retain exact permanent checker bytes as well as source/test evidence.py snapshots.
dest=OUT/'final-owned-bytes';dest.mkdir(exist_ok=True)
for p in final_paths:shutil.copyfile(p,dest/p.name)
frozen=OUT.parent/'nutriculture-p3a-review-f1-successor'
manifest=next(p for p in frozen.iterdir() if p.name.startswith('MANIFEST'))
assert sha(manifest)=='1562fbc72421466659e22fd34059e9331ecf1484de267619bb54eca84cae02ff'
assert subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode==0
result={'baseline_count':len(base),'changed_existing':changed,'all_other_baseline_unchanged':True,'receipts':receipts,'final_files':final,'frozen_manifest_sha256':sha(manifest),'original_probes_identical':True,'snapshot_maps_verified':True,'staged_empty':True}
(OUT/'final-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
