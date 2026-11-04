import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('D:/UNiNUS Projects/AI project/uninus-nutriculture')
CARD=ROOT.parent/'uninus-nutriculture-card'
OUT=Path(__file__).parent
PY=str(ROOT/'.venv/Scripts/python.exe'); CPY=str(CARD/'.venv/Scripts/python.exe')
kind=sys.argv[1]
label=kind
kind=kind.removesuffix('-final')
env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
for key in ('TMPDIR','TMP','TEMP'):env[key]=str(OUT)
env['CHROMIUM_EXECUTABLE']='C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'
env['BROWSER_EVIDENCE_DIR']=str(OUT/'browser-evidence')
env['PYTHONPATH']=str(ROOT/'tests')+os.pathsep+str(ROOT)+os.pathsep+str(OUT)
def inventory():
 paths=[p for folder in ('custom_components','tests','tools') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 paths += [p for folder in ('tests',) for p in (CARD/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 paths += [CARD/'uninus-nutriculture-card.js', ROOT/'pyproject.toml',CARD/'package.json']
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
cwd=ROOT
if kind in ('red','green','full','bridge-postrun'):
 args=['tests' if kind=='full' else 'tests/test_p3_stage_projection.py','-v','-s','-p','no:cacheprovider']
 if kind=='bridge-postrun':env['P3A_CARD_PYTHON']=CPY
 cmd=[PY,'-B','tools/evidence.py','p3a-q1-'+label,*args]
elif kind.startswith('probe'):
 # Original assertions intact; only source ROOT adapted in separate harness copy.
 original=(OUT/'test_quality_adjacent.py').read_text()
 adapted=original.replace("ROOT=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-f1-successor/uninus-nutriculture')",'ROOT=Path('+repr(str(ROOT))+')')
 target=OUT/'test_quality_adjacent_working.py'
 if not target.exists():target.write_text(adapted)
 assert target.read_text()==adapted
 cmd=[PY,'-B','tools/evidence.py','p3a-q1-'+label,'-c',str(ROOT/'pyproject.toml'),str(target),'-v','-s','-p','no:cacheprovider']
elif kind.startswith('capture'):
 cmd=[CPY,'-B',str(OUT/'check_native_capture_ui.py')]
elif kind=='node':cwd=CARD;cmd=['node','tests/test_contract.cjs']
elif kind=='browser':cwd=CARD;cmd=[CPY,'-B','-m','unittest','discover','-s','tests','-p','test_browser.py','-v']
elif kind in ('dosing','settings'):
 cmd=[PY,'-B',str(ROOT/('tools/p3a_'+kind+'_bridge.py')),'--card',str(CARD/'uninus-nutriculture-card.js'),'--browser-python',CPY,'--output',str(OUT/(kind+'-bridge'))]
elif kind=='ruff':cmd=[str(ROOT/'.venv/Scripts/ruff.exe'),'check','custom_components','tests','tools/p3a_postrun_check.py']
elif kind=='format':cmd=[str(ROOT/'.venv/Scripts/ruff.exe'),'format','--check','custom_components','tests','tools/p3a_postrun_check.py']
else:raise ValueError(kind)
before=inventory();start=time.time()
with (OUT/(label+'.log')).open('xb') as log:
 proc=subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=420)
after=inventory()
receipt={'cwd':str(cwd),'argv':cmd,'child_exit':proc.returncode,'elapsed':time.time()-start,'source_before':before,'source_after':after,'source_equal':before==after,'raw_log_sha256':hashlib.sha256((OUT/(label+'.log')).read_bytes()).hexdigest()}
(OUT/(label+'-receipt.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps({k:v for k,v in receipt.items() if not k.startswith('source_')},indent=2));print('SOURCE_EQUAL',before==after)
print((OUT/(label+'.log')).read_text(errors='replace')[-18000:])
sys.exit(proc.returncode)
