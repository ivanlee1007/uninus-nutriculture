from pathlib import Path
import hashlib,json,os,sys,importlib.metadata as metadata
B=Path(__file__).resolve().parents[1]
O=Path(os.environ['P4B_JOIN_OUTPUT']).resolve(); R=O/(sys.argv[1] if len(sys.argv)>1 else 'attempt1')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda n:json.loads((R/n).read_bytes())
assert metadata.version('homeassistant')=='2026.10.4'
result=load('result.json');wire=load('wire.json');events=load('events.json')
assert result['exit_code']==0 and result['native_requests']==len(wire)>0
assert result['events'][:-1]==events
assert result['events'][-1]['case']=='browser_done' and result['events'][-1]['page_errors']==[]
expected=['first_native_GET','actual_policy_controls','first_native_UI_SAVE_one_commit_zero_IO','first_Save_automatic_GET_no_manual_refresh','dirty_telemetry_and_Cancel_no_write','actual_same_entry_four_stage_completed_OFF_no_leases','grant_convergence_raw_observation','native_API_sensor_binary_Card_three_truths_grant','R4_exact_DTO_expiry_combined_and_standalone_True','Q1_loaded_native_True_same_user_same_transport_demotion_purge_regrant_no_cached_True','R4_passive_native_callback_combined_and_readonly_False_without_manual_GET','hard_deadline_callback_no_GET_push_Card_revoke','healthy_new_reports_no_regrant','Card_A_policy_commit_Card_B_stale_quality_CAS_rejected_draft_kept','native_Number_settings_revision_then_stale_Card_quality_Save_rejected','native_flow_revision_then_stale_Card_quality_Save_rejected_zero_commit','real_AuthManager_revoked_user_write_denied_target_unread','held_actual_native_reply_after_real_auth_denial_privacy_owner_fence','normal_STOP_fresh_SDK_full_options_policy_numbers_reload_permit_false_new_epoch_count_zero']
assert [e['case'] for e in events]==expected
assert load('protected-denial.json')=={'denied':'Unauthorized','target_reads':[]}
exact=load('expiry-wire-exact.json');assert exact['full_DTO_equal'] and exact['expiry_bytes_equal'] and exact['api']==exact['native']
assert load('grant.json')['dto']['permit']['granted'] is True
assert load('deadline.json')['dto']['permit']['granted'] is False
fresh=load('stop-fresh-process-readback.json');assert fresh['options']==wire[-1]['options'] and fresh['effective_parameters']==fresh['status_parameters']==wire[-1]['numbers']
assert fresh['quality']['permit']['granted'] is False and fresh['quality']['completion']['state']=='none' and fresh['quality']['quality']['stable_count']==0
assert fresh['quality']['epoch']!=load('grant.json')['dto']['epoch']
assert fresh['pid']>0
before=load('source-before.json');assert before==load('source-after.json')
for name,digest in before.items():assert h(B.parent/name)==digest,name
imports=load('actual-imports.json');assert imports and 'test_p4b_native' in imports and 'test_p4b_permit' in imports
for name,row in imports.items():
 p=Path(row['path']).resolve();assert p.is_relative_to(B) or p.is_relative_to(O);assert h(p)==row['sha256']
 if name.startswith('custom_components.uninus_nutriculture'):
  parts=p.parts;source=B/Path(*parts[parts.index('custom_components'):])
 else:source=B/'tests'/(name+'.py')
 assert source.is_file() and h(source)==row['sha256'],name
multi=load('multistage.json');assert not multi['closure']['leases'] and not multi['closure']['flow_pending']
assert all(not v['owns_io'] and all(v['operations_done']) for v in multi['closure']['owners'])
assert h(B.parent/'uninus-nutriculture-card/uninus-nutriculture-card.js')=='85304603e7870baa1d31ac27f74f11b206d1a0cac24bfe281c8a1bf308c41798'
assert h(B/'custom_components/uninus_nutriculture/quality.py')=='073858b0af45d42c9854dbb08555651309a630216a9eab9202eb92d57bb41de5'
receipt={'requests':len(wire),'behavior_checkpoints':len(events),'imports':len(imports),'child_exit':result['exit_code'],'source_inputs':len(before),'sdk':metadata.version('homeassistant'),'python':sys.executable,'browser':result['events'][-1]['browser_version']}
(O/'ci-verified.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt))
