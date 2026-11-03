"""Native Node syntax/unit gate plus real Chromium suite. No HA/network access."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--evidence',default='test-results/gate/'+uuid.uuid4().hex)
args=parser.parse_args()
out=ROOT/args.evidence
out.mkdir(parents=True,exist_ok=False)
node=os.environ.get('NODE') or shutil.which('node')
if not node:
    raise SystemExit('Node executable missing')
python=sys.executable
if not importlib.util.find_spec('playwright'):
    local=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if local.exists(): python=str(local)
files=['uninus-nutriculture-card.js','tests/test_contract.cjs','tests/test_browser.py','tests/check.py','demo/index.html','package.json','hacs.json','requirements-test.txt','.github/workflows/validate.yml']
hashes={}
for name in files:
    data=(ROOT/name).read_bytes()
    target=out/'snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    hashes[name]=hashlib.sha256(data).hexdigest()
os.environ['BROWSER_EVIDENCE_DIR']=str(out/'browser')
results=[]
commands=[('node-version',[node,'--version']),('syntax',[node,'--check','uninus-nutriculture-card.js']),('unit',[node,'tests/test_contract.cjs']),('browser',[python,'-m','unittest','discover','-s','tests','-p','test_browser.py','-v'])]
for name,cmd in commands:
    with (out/f'{name}.log').open('wb') as log:
        child=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
        try: code=child.wait(timeout=120)
        except subprocess.TimeoutExpired:
            if os.name=='nt': subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=log,stderr=subprocess.STDOUT)
            else: child.kill()
            child.wait(timeout=15);code=124
    raw=(out/f'{name}.log').read_text(encoding='utf-8',errors='replace')
    print(f'[{name}] exit={code}\n{raw}',flush=True)
    result={'name':name,'command':cmd,'returncode':code}
    if name=='unit':
        expected=len(re.findall(r'^test\(', (ROOT/'tests/test_contract.cjs').read_text(encoding='utf-8'),re.M))
        match=re.search(r'# tests (\d+)',raw)
        result.update(expected_cases=expected,executed_cases=int(match[1]) if match else None)
        if not match or int(match[1])!=expected or not re.search(r'# skipped 0\b',raw): result['returncode']=1
    if name=='browser':
        expected=sum(isinstance(n,ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(ast.parse((ROOT/'tests/test_browser.py').read_text(encoding='utf-8'))))
        match=re.search(r'Ran (\d+) tests?',raw)
        result.update(expected_cases=expected,executed_cases=int(match[1]) if match else None)
        if not match or int(match[1])!=expected or 'skipped=' in raw: result['returncode']=1
    results.append(result)
    (out/'result.json').write_text(json.dumps({'sha256':hashes,'results':results},indent=2),encoding='utf-8')
    if result['returncode']: raise SystemExit(result['returncode'])
print(f'All native gates passed. Evidence: {out}')
