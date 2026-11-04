import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-f1-successor')
OUT=Path(__file__).parent
PY='D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe'
kind=sys.argv[1]
env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
for key in ('TMPDIR','TMP','TEMP'): env[key]=str(OUT)
env['CHROMIUM_EXECUTABLE']='C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'
env['BROWSER_EVIDENCE_DIR']=str(OUT/'browser-evidence')
env['PYTHONPATH']=str(ROOT/'uninus-nutriculture/tests')+os.pathsep+str(ROOT/'uninus-nutriculture')+os.pathsep+str(OUT)
def inventory():
 return {str(f.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
before=inventory()
if kind in ('browser','browser-current'):
 cwd=ROOT/'uninus-nutriculture-card';cmd=['D:/UNiNUS Projects/AI project/uninus-nutriculture-card/.venv/Scripts/python.exe','-B','-m','unittest','discover','-s','tests','-p','test_browser.py','-v']
elif kind=='probe':
 cwd=ROOT/'uninus-nutriculture';cmd=[PY,'-B','-m','pytest','-c',str(cwd/'pyproject.toml'),str(OUT/'test_quality_adjacent.py'),'-v','-s','-p','no:cacheprovider','--basetemp',str(OUT/'pytest-probe')]
else: raise ValueError(kind)
start=time.time()
with (OUT/(kind+'.log')).open('wb') as log:
 result=subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=420)
after=inventory();receipt={'cwd':str(cwd),'argv':cmd,'child_exit':result.returncode,'elapsed':time.time()-start,'source_before':before,'source_after':after,'source_equal':before==after,'raw_log_sha256':hashlib.sha256((OUT/(kind+'.log')).read_bytes()).hexdigest()}
(OUT/(kind+'-receipt.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps({k:v for k,v in receipt.items() if not k.startswith('source_')},indent=2));print('SOURCE_EQUAL',before==after)
print((OUT/(kind+'.log')).read_text(errors='replace')[-18000:])
sys.exit(result.returncode)
