import hashlib,json
from pathlib import Path
OUT=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((OUT/'baseline.json').read_text())
snap=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-f1-successor')
old=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-20261103-224149')
for key,root in [('successor',snap),('prior',old)]:
    assert sha(root/'MANIFEST.json')==base[key]['manifest_sha256']
    assert {k:sha(root/k) for k in base[key]['files']}==base[key]['files']
for root,files in base['historical_evidence'].items():
    assert {p.name:sha(p) for p in Path(root).iterdir() if p.is_file()}==files
runs={}
for name in ['focused','focused-retry','focused-final','full','node']:
    r=json.loads((OUT/(name+'-receipt.json')).read_text())
    assert r['pre']==r['post']==base
    assert r['same_all_135_and_historical']
    assert sha(OUT/(name+'.log'))==r['raw_log_sha256']
    runs[name]={'child_exit':r['child_exit'],'raw_log_sha256':r['raw_log_sha256']}
assert all(runs[n]['child_exit']==0 for n in ['focused-final','full','node'])
assert all(runs[n]['child_exit']==1 for n in ['focused','focused-retry'])
assert sha(OUT/'test_review_probe.py')=='3839c83f3573f7525ffa0ed2f6b46dca887b78c02e8fc7392c3324da93a4c7ad'
delta=json.loads((OUT/'delta.json').read_text())
assert set(delta['changed'])=={'uninus-nutriculture/custom_components/uninus_nutriculture/control.py','uninus-nutriculture/docs/P3A_LOCAL_CHECKPOINT.json'}
assert len(delta['added'])==2 and not delta['removed']
# All potentially consumed source/test/config/runner bytes, not only modified files.
consumed={}
for p,digest in base['successor']['files'].items():
    if p.startswith(('uninus-nutriculture/custom_components/','uninus-nutriculture/tests/')) or p in ['uninus-nutriculture/pyproject.toml','uninus-nutriculture/requirements-test.txt','uninus-nutriculture/tools/evidence.py','uninus-nutriculture/tools/p3a_dosing_bridge.py','uninus-nutriculture/tools/p3a_settings_bridge.py','uninus-nutriculture-card/uninus-nutriculture-card.js','uninus-nutriculture-card/tests/test_contract.cjs']:
        consumed[p]=digest
result={'verdict':'PASS','scope':'joint P3a SPEC exact successor; not quality/publication/full P3 approval','successor_manifest_sha256':base['successor']['manifest_sha256'],'successor_files':len(base['successor']['files']),'prior_files':len(base['prior']['files']),'all_source_and_historical_evidence_unchanged':True,'covered_consumed_inputs':consumed,'covered_consumed_count':len(consumed),'runs':runs,'reviewer_harnesses':{p.name:sha(p) for p in OUT.glob('*.py')},'artifacts':{p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='final-verification.json'}}
(OUT/'final-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['covered_consumed_inputs','reviewer_harnesses','artifacts']},indent=2))
