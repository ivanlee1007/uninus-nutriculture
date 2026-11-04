from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1]
p=root/'custom_components/uninus_nutriculture/nutrient.py';s=p.read_text().replace('if self.role in self.targets else asyncio.sleep(0)','if self.role in self.bindings else asyncio.sleep(0)');p.write_text(s,newline='\n')
p=root.parent/'uninus-nutriculture-card/uninus-nutriculture-card.js';s=p.read_text();a='    updateControls() {\n      const v3=';b='''    updateControls() {
      this.p3bRows=this.p3bRows||new Map();
      for(const key of ['acid_enabled','mix_enabled']){
        if(this.controlRows.has(key))this.p3bRows.set(key,this.controlRows.get(key));
        if(this.status()?.attributes?.schema_version===4){if(this.p3bRows.has(key))this.controlRows.set(key,this.p3bRows.get(key));}
        else if(this.controlRows.has(key)){this.controlRows.get(key).el.remove();this.controlRows.delete(key);}
      }
      const v3=''';assert a in s;s=s.replace(a,b)
s=s.replace("['parameters','dosing_parameters','acid_parameters','mix_parameters','safety_parameters'].every(k=>JSON.stringify(a[k])===JSON.stringify(b[k]))","['parameters','dosing_parameters','acid_parameters','mix_parameters','safety_parameters'].every(k=>b[k]===null?a[k]===null:a[k]!==null&&Object.keys(b[k]).every(key=>a[k]?.[key]===b[k][key]))")
p.write_text(s,newline='\n')
# Receipts compare untouched original and frozen review sources to the supplied baseline.
base=json.loads((root.parent/'BASELINE.json').read_text());before=base['base_files']
original=Path('D:/UNiNUS Projects/AI project')
frozen=Path(base['base_manifest']).parent
results={}
for name,folder in [('original',original),('frozen',frozen)]:
 rows={};missing=[]
 for rel,expected in before.items():
  p=folder/rel
  if p.is_file():rows[rel]={'expected':expected,'actual':hashlib.sha256(p.read_bytes()).hexdigest()}
  else:missing.append(rel)
 results[name]={'checked':len(rows),'mismatch':{k:v for k,v in rows.items() if v['expected']!=v['actual']},'missing':missing}
results['manifest']={'expected':base['base_manifest_sha256'],'actual':hashlib.sha256(Path(base['base_manifest']).read_bytes()).hexdigest()}
(root/'docs/P3B_READONLY_RECEIPTS.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
