import os, sys, json, subprocess, hashlib, time
from pathlib import Path
ROOT=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-20261103-224149')
OUT=Path(__file__).parent
PY='D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe'
CPY='D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe'
def hashes():
 m=json.loads((ROOT/'MANIFEST.json').read_text()); return {k:hashlib.sha256((ROOT/k).read_bytes()).hexdigest() for k in m['files']}
mode=sys.argv[1]
backend=ROOT/'uninus-nutriculture'; card=ROOT/'uninus-nutriculture-card'
if mode=='native': cmd=[PY,'-B','-m','pytest','tests','-q','-p','no:cacheprovider','--basetemp',str(OUT/'pytest-native')]; cwd=backend
elif mode=='node': cmd=['node','tests/test_contract.cjs']; cwd=card
elif mode=='probe': cmd=[PY,'-B','-m','pytest','-c',str(backend/'pyproject.toml'),str(OUT/'test_review_probe.py'),'-v','-s','-p','no:cacheprovider','--basetemp',str(OUT/'pytest-probe')]; cwd=backend
elif mode in ('dosing-bridge','dosing-bridge-retry'): cmd=[PY,'-B',str(backend/'tools/p3a_dosing_bridge.py'),'--card',str(card/'uninus-nutriculture-card.js'),'--browser-python',CPY,'--output',str(OUT/mode)]; cwd=backend
else: raise SystemExit(mode)
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(OUT),TEMP=str(OUT),TMP=str(OUT),PYTHONPATH=os.pathsep.join([str(backend/'tests'),str(backend)]))
pre=hashes(); started=time.time()
receipt={'mode':mode,'command':cmd,'cwd':str(cwd),'before':pre,'started':started}
(OUT/(mode+'-receipt.json')).write_text(json.dumps(receipt,indent=2))
with (OUT/(mode+'.log')).open('w',encoding='utf-8') as log:
 try:
  child=subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
  receipt['child_exit']=child.returncode
 except Exception as exc: receipt['runner_error']=repr(exc)
receipt.update(after=hashes(),elapsed=time.time()-started)
receipt['unchanged']=pre==receipt['after']
(OUT/(mode+'-receipt.json')).write_text(json.dumps(receipt,indent=2))
print({k:v for k,v in receipt.items() if k not in ('before','after')})
print((OUT/(mode+'.log')).read_text(encoding='utf-8')[-12000:])
