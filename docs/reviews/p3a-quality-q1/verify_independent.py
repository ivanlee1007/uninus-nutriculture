from pathlib import Path
import hashlib,json,difflib,re
O=Path(__file__).parent; S=O.parent; Q=S/'nutriculture-p3a-review-q1-successor'; P=S/'nutriculture-p3a-review-f1-successor'; SPEC=S/'p3a-spec-q1-recheck'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text(encoding='utf-8'))
a=load(P/'MANIFEST.json')['files']; b=load(Q/'MANIFEST.json')['files']
changed=[k for k in a if a[k]!=b[k]];added=sorted(b.keys()-a.keys());removed=sorted(a.keys()-b.keys())
assert not removed
assert sorted(changed)==sorted(['uninus-nutriculture/custom_components/uninus_nutriculture/nutrient.py','uninus-nutriculture/custom_components/uninus_nutriculture/sensor.py','uninus-nutriculture/docs/P3A_LOCAL_CHECKPOINT.json'])
diff=''.join(''.join(difflib.unified_diff((P/k).read_text().splitlines(True),(Q/k).read_text().splitlines(True),fromfile='prior/'+k,tofile='successor/'+k)) for k in changed)
(O/'reviewed-source-diff.txt').write_text(diff,encoding='utf-8')
sp=load(SPEC/'source-pre.json');so=load(SPEC/'source-post.json');assert sp==so
assert sp['successor']['files']==b and sp['prior']['files']==a
spec={}
for label,expected in [('postrun','4 passed'),('probe','3 passed'),('capture','"controls_attached": true')]:
 r=load(SPEC/(label+'-receipt.json'));log=SPEC/r['log'];assert r['child_exit']==0 and r['source_unchanged'] and r['source_count']==138
 assert sha(log)==r['raw_log_sha256'] and expected in log.read_text()
 for k,v in r['harness_inputs'].items():
  path=Path(k)
  if sha(path)!=v:
   assert path.name=='run_recheck.py' and sha(SPEC/'run_recheck_v1.py')==v
 spec[label]={'child_exit':0,'raw_sha256':sha(log)}
for label,expected in [('postrun','4 passed'),('probe','3 passed'),('capture','"controls_attached": true')]:
 r=load(O/(label+'-receipt.json'));assert r['child_exit']==0 and r['source_unchanged'];assert sha(O/r['log'])==r['raw_log_sha256']
 assert expected in (O/r['log']).read_text()
 for k,v in r['harness_inputs'].items():assert sha(Path(k))==v
# Every overlay is only the declared frozen root substitution, not an assertion edit.
for name in ['test_quality_adjacent.py','check_native_capture_ui.py']:
 orig=S/'p3a-quality-review-20261103'/name
 assert sha(O/name)==sha(orig)
 overlay=O/(Path(name).stem+'_successor.py')
 assert overlay.read_text().replace('nutriculture-p3a-review-q1-successor','nutriculture-p3a-review-f1-successor')==orig.read_text()
assert sha(O/'run_recheck_spec_original.py')==sha(SPEC/'run_recheck.py')
ui=load(O/'post-run-shipped-ui.json');cap=O/'post-run-master-off.json';assert sha(cap)==ui['native_capture_sha256'];assert ui['controls_attached'] and not ui['page_errors']
assert ui['shipped_sha256']==b['uninus-nutriculture-card/uninus-nutriculture-card.js']
summary={'changed':changed,'added':added,'removed':removed,'spec_prepost_equal':True,'spec_receipts_authenticated':spec,'own_receipts_authenticated':3,'overlays_path_only':True,'prior_manifest_sha256':sha(P/'MANIFEST.json'),'successor_manifest_sha256':sha(Q/'MANIFEST.json'),'source_diff_sha256':sha(O/'reviewed-source-diff.txt')}
(O/'independent-authentication.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2));print(diff)
