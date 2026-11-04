"""Independent read-only exact-successor SPEC recheck."""
import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
OUT=Path(__file__).parent
SNAP=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-f1-successor')
OLD=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-20261103-224149')
ORIG=Path('C:/Users/ivanl/.hermes/cache/scratch/p3a-spec-review-20261103')
REPAIR=Path('C:/Users/ivanl/.hermes/cache/scratch/p3a-f1-repair-20261103')
ROOT=SNAP/'uninus-nutriculture'
PY='D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(root):
    m=json.loads((root/'MANIFEST.json').read_text())
    actual={k:sha(root/k) for k in m['files']}
    assert actual==m['files'], 'manifest files mismatch'
    return {'manifest_sha256':sha(root/'MANIFEST.json'),'files':actual}
def sealed():
    return {str(d):{p.name:sha(p) for p in d.iterdir() if p.is_file()} for d in [ORIG,REPAIR]}
def state(): return {'successor':inventory(SNAP),'prior':inventory(OLD),'historical_evidence':sealed()}
def save(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2),encoding='utf-8')
mode=sys.argv[1]
if mode=='setup':
    assert not (OUT/'baseline.json').exists()
    s=state()
    assert s['successor']['manifest_sha256']=='1562fbc72421466659e22fd34059e9331ecf1484de267619bb54eca84cae02ff'
    assert s['prior']['manifest_sha256']=='68bb90f7d1c19439b3e93a41f582b4ac0e6fd0f9845b69e55124e01162ac0ab3'
    shutil.copyfile(ORIG/'test_review_probe.py',OUT/'test_review_probe.py')
    assert sha(OUT/'test_review_probe.py')=='3839c83f3573f7525ffa0ed2f6b46dca887b78c02e8fc7392c3324da93a4c7ad'
    a=s['prior']['files']; b=s['successor']['files']
    save('delta.json',{'changed':{k:{'prior':a[k],'successor':b[k]} for k in a if a[k]!=b[k]},'added':{k:b[k] for k in b.keys()-a.keys()},'removed':list(a.keys()-b.keys())})
    save('baseline.json',s)
    (OUT/'CHECKPOINT.md').write_text('# SPEC F1 recheck in progress\nExact 135-file successor and prior 133-file manifest verified; historical top-level review/repair evidence sealed. Probe copied byte-identically into this exclusive output. No verdict yet.\n',encoding='utf-8')
    print('setup verified',len(b),'successor files and',len(a),'prior files')
    sys.exit(0)
base=json.loads((OUT/'baseline.json').read_text())
pre=state(); assert pre==base
if mode=='focused':
    cmd=[PY,'-B','-m','pytest','-c',str(ROOT/'pyproject.toml'),str(ROOT/'tests/test_p3_fault_codes.py'),str(OUT/'test_review_probe.py'),str(OUT/'test_adjacent.py'),'-v','-s','-p','no:cacheprovider','--basetemp',str(OUT/'pytest-focused')]
elif mode=='full':
    cmd=[PY,'-B','-m','pytest','tests','-q','-p','no:cacheprovider','--basetemp',str(OUT/'pytest-full')]
elif mode=='node':
    cmd=['node',str(SNAP/'uninus-nutriculture-card/tests/test_contract.cjs')]
else: raise SystemExit(mode)
assert not (OUT/(mode+'.log')).exists(), 'sealed label'
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(OUT),TEMP=str(OUT),TMP=str(OUT),PYTHONPATH=os.pathsep.join([str(ROOT/'tests'),str(ROOT)]))
start=time.time()
with (OUT/(mode+'.log')).open('wb') as log:
    p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
post=state()
r={'argv':cmd,'cwd':str(ROOT),'environment':{k:env[k] for k in ['PYTHONDONTWRITEBYTECODE','TMPDIR','TEMP','TMP','PYTHONPATH']},'child_exit':p.returncode,'seconds':time.time()-start,'pre':pre,'post':post,'same_all_135_and_historical':pre==post==base,'probe_sha256':sha(OUT/'test_review_probe.py'),'raw_log_sha256':sha(OUT/(mode+'.log'))}
save(mode+'-receipt.json',r)
print(json.dumps({k:v for k,v in r.items() if k not in ['pre','post']},indent=2))
print((OUT/(mode+'.log')).read_text(errors='replace')[-18000:])
assert pre==post==base
sys.exit(p.returncode)
