import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path('D:/UNiNUS Projects/AI project/uninus-nutriculture')
OUT=Path(__file__).parent
FROZEN=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-20261103-224149')
ORIGINAL=Path('C:/Users/ivanl/.hermes/cache/scratch/p3a-spec-review-20261103')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((OUT/'baseline.json').read_text())
manifest=json.loads((FROZEN/'MANIFEST.json').read_text())
assert {k:sha(FROZEN/k) for k in manifest['files']} == manifest['files']
assert sha(FROZEN/'MANIFEST.json') == '68bb90f7d1c19439b3e93a41f582b4ac0e6fd0f9845b69e55124e01162ac0ab3'
assert {str(p.relative_to(ORIGINAL)):sha(p) for p in ORIGINAL.iterdir() if p.is_file()} == base['original']
gates={}
for mode in ('native','probe','node','quality','format','bridge','settings-bridge'):
    receipt=json.loads((OUT/(mode+'-receipt.json')).read_text())
    assert receipt['child_exit']==0
    assert receipt['pre']==receipt['post']==base['source']
    assert all(receipt[k] for k in ('same_source','original_evidence_unchanged','frozen_unchanged','original_probe_byte_identical'))
    gates[mode]={'exit':receipt['child_exit'],'receipt_sha256':sha(OUT/(mode+'-receipt.json')),'log_sha256':sha(OUT/(mode+'.log'))}
for key,value in base['source'].items():
    part,rel=key.split('/',1)
    path=(ROOT if part=='backend' else ROOT.parent/'uninus-nutriculture-card')/rel
    assert sha(path)==value
for label,code in [('p3a-f1-01-native-red',1),('p3a-f1-02-native-green',0),('p3a-f1-03-native-full',0),('p3a-f1-04-original-probe',0)]:
    run=json.loads((ROOT/'docs/evidence'/label/'run.json').read_text())
    assert run['returncode']==code
    for key,value in run['sha256'].items():
        assert sha(ROOT/'docs/evidence'/label/'snapshot'/key)==value
    if code==0:
        for key,value in run['sha256'].items(): assert sha(ROOT/key)==value
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT).strip()
probe=json.loads((OUT/'provider-counterexample.json').read_text())
assert probe=={'accepted':True,'fault_length':16,'persisted_equals_provider':False,'sensor_equals_provider':False,'all_outputs_off':True,'running':False,'flow_state':'fault'}
result={'frozen_files_verified':len(manifest['files']),'consumed_inputs_verified':len(base['source']),'original_evidence_unchanged':True,'all_green_snapshots_match_current_bytes':True,'gates':gates,'control_sha256':sha(ROOT/'custom_components/uninus_nutriculture/control.py'),'new_test_sha256':sha(ROOT/'tests/test_p3_fault_codes.py'),'original_probe_sha256':sha(ORIGINAL/'test_review_probe.py'),'copied_probe_sha256':sha(OUT/'test_review_probe.py'),'new_test_cases':7,'full_native_cases':245,'staged_files':[]}
(OUT/'final-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
