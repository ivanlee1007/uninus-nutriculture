from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def edit(n,a,b):
 p=ROOT/'custom_components/uninus_nutriculture'/n;s=p.read_text();assert a in s,(n,a[:60]);p.write_text(s.replace(a,b),newline='\n')
edit('control.py','            if self.supports_nutrient and not self.execution_stage.owns_io:','            for name in ("acid", "mix"):\n                stage=getattr(self,name+"_stage")\n                if getattr(self,"supports_"+name) and not stage.owns_io:\n                    roles=("acid","circulation") if name=="acid" else ("circulation",)\n                    stage.bindings={role:dict(config[role+"_binding"]) for role in roles}\n                    stage.targets={role:resolve(self.hass,binding) for role,binding in stage.bindings.items()}\n                    stage.operations={}\n                    stage.owns_io=True\n                    await stage.cleanup("fault")\n            if self.supports_nutrient and not self.execution_stage.owns_io:')
# Fix Options global S authority and reject unrecognized schema versions.
edit('config_flow.py','                            mix_parameters=mix if new_stage or self.config_entry.options.get("control_contract_version") == 4 else None,','                            mix_parameters=mix if new_stage or self.config_entry.options.get("control_contract_version") == 4 else None,\n                            safety_parameters={k:user_input.get(k,self.config_entry.options.get("safety_parameters", {}).get(k,self.config_entry.options.get("dosing_parameters",{}).get(k,DEFAULTS[k]))) for k in SAFETY_KEYS} if new_stage or self.config_entry.options.get("control_contract_version") == 4 else None,')
edit('manager.py','        options = dict(self.entry.options)','        options = dict(self.entry.options)\n        if options.get("control_contract_version",3) not in (3,4):\n            raise ServiceValidationError("settings_schema_mismatch")')
edit('control.py','        if not self.tank.active or key not in (','        if self.tank.entry.options.get("control_contract_version",3) not in (3,4):\n            raise ServiceValidationError("settings_schema_mismatch")\n        if not self.tank.active or key not in (')
edit('control.py','        generation = self.generation\n        stopping_at_request','        if self.tank.entry.options.get("control_contract_version",3) not in (3,4):\n            raise ServiceValidationError("settings_schema_mismatch")\n        generation = self.generation\n        stopping_at_request')
# Copy bridge into a NEW P3b tool; historical P3a source remains untouched.
s=(ROOT/'tools/p3a_postrun_check.py').read_text().replace('["uninus_nutriculture", "apply_control_settings"]','["uninus_nutriculture", "apply_control_settings_v4"]')
(ROOT/'tools/p3b_postrun_check.py').write_text(s,newline='\n')
# Add exact before/after receipts to future P3b evidence runs only.
p=ROOT/'tools/evidence.py';s=p.read_text();s=s.replace('            "sha256": hashes,','            "sha256": hashes,\n            "source_after": {rel:hashlib.sha256((root/rel).read_bytes()).hexdigest() for rel in hashes},')
p.write_text(s,newline='\n')
# services YAML + translation labels; additive, no changes to old labels.
p=ROOT/'custom_components/uninus_nutriculture/services.yaml';s=p.read_text();s+='\napply_control_settings_v4:\n  name: Apply schema4 control settings\n  description: Atomic revision-checked settings; null stage maps preserve uncommissioned drafts.\n  fields:\n'
for key in ('config_entry_id','expected_revision','parameters','dosing_parameters','acid_parameters','mix_parameters','safety_parameters','allowed_weekdays'):
 s+=f'    {key}:\n      required: true\n      selector:\n        object:\n' if key not in ('config_entry_id','expected_revision') else f'    {key}:\n      required: true\n      selector:\n        '+('text:\n' if key=='config_entry_id' else 'number:\n          min: 0\n          mode: box\n')
p.write_text(s,newline='\n')
from importlib.util import spec_from_file_location,module_from_spec
sp=spec_from_file_location('ds',ROOT/'custom_components/uninus_nutriculture/dosing_settings.py')
# Do not import HA through a non-HA tool interpreter; labels are the literal contract fields.
fields=['acid_output','acid_commissioned','acid_device_max_on_seconds','acid_protection_confirmed','acid_alias_notes','acid_sample_mode','acid_sample_attribute','acid_report_contract_confirmed','mix_commissioned','circulation_device_max_on_seconds','circulation_protection_confirmed','circulation_alias_notes']
q=['safe_min_level_m','pulse_seconds','max_total_on_seconds','max_pulses','post_mix_seconds','sample_wait_timeout_seconds','stable_samples','stable_interval_seconds','flow_timeout_seconds']
fields += ['acid_'+k for k in q]+['mix_safe_min_level_m','mix_flow_timeout_seconds']
for rel in ('strings.json','translations/en.json','translations/zh-Hant.json'):
 p=ROOT/'custom_components/uninus_nutriculture'/rel;d=json.loads(p.read_text());data=d['options']['step']['init']['data'];data.update({k:k.replace('_',' ') for k in fields});p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',newline='\n')
