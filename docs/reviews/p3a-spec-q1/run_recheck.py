"""Read-only exact Q1 successor recheck; all writes exclusive OUT."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
OUT=Path(__file__).parent
SCR=OUT.parent
SNAP=SCR/'nutriculture-p3a-review-q1-successor'
ROOT=SNAP/'uninus-nutriculture'
PRIOR=SCR/'nutriculture-p3a-review-f1-successor'
QUALITY=SCR/'p3a-quality-review-20261103'
REPAIR=SCR/'p3a-q1-repair-20261103'
PY='D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe'
CARD='D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v):(OUT/n).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def inventory(root):
 m=json.loads((root/'MANIFEST.json').read_text());a={k:sha(root/k) for k in m['files']};assert a==m['files'];return {'manifest_sha256':sha(root/'MANIFEST.json'),'files':a}
def state():
 return {'successor':inventory(SNAP),'prior':inventory(PRIOR),'sealed':{str(d):{str(p.relative_to(d)):sha(p) for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts} for d in [QUALITY,REPAIR,SCR/'p3a-spec-f1-recheck']}}
def historical():
 results={}
 expected=inventory(SNAP)['files']
 for p in REPAIR.glob('*-receipt.json'):
  r=json.loads(p.read_text());label=p.name.removesuffix('-receipt.json');log=REPAIR/(label+'.log');assert sha(log)==r['raw_log_sha256'];assert r['source_before']==r['source_after']
  deltas=[]
  for k,v in r['source_before'].items():
   rel=None
   for repo in ['uninus-nutriculture','uninus-nutriculture-card']:
    marker=repo+'/'
    norm=k.replace('\\','/')
    if marker in norm:rel=marker+norm.split(marker,1)[1];break
   assert rel in expected,rel
   if expected[rel]!=v:deltas.append(rel)
  assert len(r['source_before'])==83
  assert r['child_exit']==(1 if label in ['red','probe-red','capture-red'] else 0)
  if label in ['full-final','bridge-postrun-final','ruff-final','format-final']:assert not deltas
  if label in ['browser','node','dosing','settings','probe-green','capture-green']:assert deltas==['uninus-nutriculture/tests/test_p3_stage_projection.py']
  results[label]={'child_exit':r['child_exit'],'raw_log_sha256':sha(log),'inventory_count':len(r['source_before']),'broad_inventory_deltas':deltas}
 save('historical-gates.json',results);return results
mode=sys.argv[1]
if mode=='setup':
 assert not (OUT/'source-pre.json').exists();s=state();assert s['successor']['manifest_sha256']=='9dd070aa362481bcbda54c8e20a392bbe3875fa4d4ecbe7bb743fe8b3a17d6f0';save('source-pre.json',s)
 a=s['prior']['files'];b=s['successor']['files'];save('delta.json',{'changed':{k:[a[k],b[k]] for k in a if a[k]!=b[k]},'added':list(b.keys()-a.keys()),'removed':list(a.keys()-b.keys())})
 for f in ['test_quality_adjacent.py','check_native_capture_ui.py']:
  shutil.copyfile(QUALITY/f,OUT/f);assert sha(QUALITY/f)==sha(OUT/f)
 old='nutriculture-p3a-review-f1-successor';new='nutriculture-p3a-review-q1-successor'
 for f in ['test_quality_adjacent.py','check_native_capture_ui.py']:
  text=(OUT/f).read_text();assert text.count(old)==1
  overlay=OUT/(Path(f).stem+'_successor.py');overlay.write_text(text.replace(old,new),encoding='utf-8');assert overlay.read_text().replace(new,old)==text
 historical();(OUT/'CHECKPOINT.md').write_text('# Q1 SPEC recheck in progress\n138 successor files and prior135 validated. Original scripts copied byte-exact, separate successor-only path overlays created. Original quality/repair/F1 artifacts sealed. Historical broad inventories checked separately from actual consumed scope. No verdict yet.\n',encoding='utf-8');print('setup PASS',len(b));sys.exit()
base=json.loads((OUT/'source-pre.json').read_text());pre=state();assert pre==base
if mode=='postrun':
 args=[str(ROOT/'tests/test_p3_stage_projection.py')]
elif mode=='probe':args=[str(OUT/'test_quality_adjacent_successor.py'),str(OUT/'test_adjacent.py')]
elif mode=='capture':args=None
elif mode=='verify':
 post=state();assert post==base;save('source-post.json',post);h=historical();rr={}
 for p in OUT.glob('*-receipt.json'):
  r=json.loads(p.read_text());assert r['child_exit']==0;assert r['source_unchanged'];assert sha(OUT/r['log'])==r['raw_log_sha256'];rr[p.name]={'child_exit':r['child_exit'],'raw_log_sha256':r['raw_log_sha256']}
 save('final-verification.json',{'source_unchanged':True,'source_count':len(post['successor']['files']),'manifest_sha256':post['successor']['manifest_sha256'],'historical_gates':h,'reviewer_gates':rr});print('VERIFIED',len(post['successor']['files']),len(h),rr);sys.exit()
else:raise SystemExit(mode)
if mode=='capture':cmd=[CARD,'-B',str(OUT/'check_native_capture_ui_successor.py')]
else:cmd=[PY,'-B','-m','pytest','-c',str(ROOT/'pyproject.toml'),*args,'-v','-s','-p','no:cacheprovider','--basetemp',str(OUT/('pytest-'+mode))]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(OUT),TEMP=str(OUT),TMP=str(OUT),PYTHONPATH=os.pathsep.join([str(ROOT/'tests'),str(ROOT)]),P3A_CARD_PYTHON=CARD,CHROMIUM_EXECUTABLE='C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe')
log=OUT/(mode+'.log');assert not log.exists();began=time.time()
with log.open('wb') as f:p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
post=state();r={'argv':cmd,'cwd':str(ROOT),'environment':{k:env[k] for k in ['PYTHONPATH','P3A_CARD_PYTHON','CHROMIUM_EXECUTABLE','TMPDIR']},'child_exit':p.returncode,'seconds':time.time()-began,'source_unchanged':pre==post==base,'source_count':len(post['successor']['files']),'log':log.name,'raw_log_sha256':sha(log),'harness_inputs':{str(q):sha(q) for q in OUT.glob('*.py')}};save(mode+'-receipt.json',r);print(json.dumps(r,indent=2));print(log.read_text(errors='replace')[-22000:]);assert pre==post==base;sys.exit(p.returncode)
