"""Owned evidence runner; no original review output is ever overwritten."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path('D:/UNiNUS Projects/AI project/uninus-nutriculture')
CARD = Path('D:/UNiNUS Projects/AI project/uninus-nutriculture-card')
OUT = Path(__file__).parent
ORIGINAL = Path('C:/Users/ivanl/.hermes/cache/scratch/p3a-spec-review-20261103')
FROZEN = Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-20261103-224149')
PY = str(ROOT / '.venv/Scripts/python.exe')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def original_hashes():
    return {str(p.relative_to(ORIGINAL)): digest(p) for p in ORIGINAL.iterdir() if p.is_file()}

def consumed():
    paths = []
    for directory in ('custom_components', 'tests'):
        paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.extend(ROOT / n for n in ('pyproject.toml', 'requirements-test.txt', 'tools/evidence.py', 'tools/p3a_dosing_bridge.py', 'tools/p3a_settings_bridge.py'))
    result = {'backend/' + str(p.relative_to(ROOT)).replace('\\', '/'): digest(p) for p in paths}
    for p in [CARD/'uninus-nutriculture-card.js', CARD/'tests/test_contract.cjs']:
        result['card/' + str(p.relative_to(CARD)).replace('\\', '/')] = digest(p)
    return result

def frozen_hashes():
    manifest = json.loads((FROZEN/'MANIFEST.json').read_text())
    result = {p: digest(FROZEN / p) for p in manifest['files']}
    return {'manifest_sha256': digest(FROZEN/'MANIFEST.json'), 'files': result}

mode = sys.argv[1]
if mode == 'setup':
    shutil.copyfile(ORIGINAL/'test_review_probe.py', OUT/'test_review_probe.py')
    assert digest(ORIGINAL/'test_review_probe.py') == digest(OUT/'test_review_probe.py')
    baseline = {'original': original_hashes(), 'frozen': frozen_hashes(), 'source': consumed(), 'probe_sha256': digest(OUT/'test_review_probe.py')}
    (OUT/'baseline.json').write_text(json.dumps(baseline, indent=2))
    print('captured baseline', len(baseline['source']), 'consumed inputs;', len(baseline['frozen']['files']), 'frozen files; probe', baseline['probe_sha256'])
    sys.exit(0)
base = json.loads((OUT/'baseline.json').read_text())
if mode == 'native':
    cmd = [PY, '-B', 'tools/evidence.py', 'p3a-f1-03-native-full', 'tests', '-q', '-p', 'no:cacheprovider']
elif mode == 'probe':
    cmd = [PY, '-B', 'tools/evidence.py', 'p3a-f1-04-original-probe', '-c', str(ROOT/'pyproject.toml'), str(OUT/'test_review_probe.py'), '-v', '-s', '-p', 'no:cacheprovider']
elif mode == 'node':
    cmd = ['node', str(CARD/'tests/test_contract.cjs')]
elif mode == 'quality':
    cmd = [PY, '-m', 'ruff', 'check', 'custom_components', 'tests']
elif mode == 'format':
    cmd = [PY, '-m', 'ruff', 'format', '--check', 'custom_components', 'tests']
elif mode == 'settings-bridge':
    cmd = [PY, '-B', 'tools/p3a_settings_bridge.py', '--card', str(CARD/'uninus-nutriculture-card.js'), '--browser-python', str(CARD/'.venv/Scripts/python.exe'), '--output', str(OUT/'settings-bridge')]
elif mode == 'bridge':
    cmd = [PY, '-B', 'tools/p3a_dosing_bridge.py', '--card', str(CARD/'uninus-nutriculture-card.js'), '--browser-python', str(CARD/'.venv/Scripts/python.exe'), '--output', str(OUT/'bridge')]
else:
    raise SystemExit(mode)
pre = consumed()
assert pre == base['source'], 'source changed from setup baseline'
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(OUT), TEMP=str(OUT), TMP=str(OUT), PYTHONPATH=os.pathsep.join([str(ROOT/'tests'), str(ROOT)]))
env['CHROMIUM_EXECUTABLE'] = 'C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe'
start = time.time()
with (OUT/(mode+'.log')).open('wb') as log:
    proc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
post = consumed()
receipt = {'command': cmd, 'cwd': str(ROOT), 'child_exit': proc.returncode, 'elapsed_seconds': time.time()-start, 'pre': pre, 'post': post, 'same_source': pre == post, 'original_evidence_unchanged': original_hashes() == base['original'], 'frozen_unchanged': frozen_hashes() == base['frozen'], 'original_probe_byte_identical': digest(OUT/'test_review_probe.py') == base['probe_sha256'], 'raw_log_sha256': digest(OUT/(mode+'.log'))}
(OUT/(mode+'-receipt.json')).write_text(json.dumps(receipt, indent=2))
print(json.dumps({k:v for k,v in receipt.items() if k not in ('pre','post')}, indent=2))
print((OUT/(mode+'.log')).read_text(errors='replace')[-10000:])
assert all(receipt[k] for k in ('same_source','original_evidence_unchanged','frozen_unchanged','original_probe_byte_identical'))
sys.exit(proc.returncode)
