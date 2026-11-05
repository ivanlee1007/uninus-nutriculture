import json,os,sys,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
G=Path(__file__).resolve().parents[2]; CARD=G/'uninus-nutriculture-card'; counter=0

def rpc(kind,payload=None):
 global counter
 counter+=1
 print(json.dumps(dict(id=counter,kind=kind,payload=payload)),flush=True)
 line=sys.stdin.readline(4*1024*1024+1)
 if len(line)>4*1024*1024: raise RuntimeError('IPC oversized')
 r=json.loads(line)
 if 'harness_error' in r: raise RuntimeError(r['harness_error'])
 return r

def main():
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_EXECUTABLE') or None)
  try:
   p=browser.new_page(viewport={'width':768,'height':1200}); p.set_default_timeout(9000)
   errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   p.set_content('<!doctype html><meta charset="utf-8"><body>');p.evaluate('console.log=console.info=console.warn=console.error=()=>{}')
   p.expose_function('nativeRPC',rpc);p.add_script_tag(path=str(CARD/'uninus-nutriculture-card.js'))
   rpc('multistage_prepare')
   p.evaluate('''async()=>{
    await customElements.whenDefined('uninus-nutriculture-card'); window.cards={};window.receipts=[];window.pending=0;
    window.refreshCard=(name,s)=>{cards[name].hass={states:s.states,services:s.services,user:cards[name]._nativeUser||(cards[name]._nativeUser={id:s.user_id,is_admin:true,is_active:true}),connection:cards[name]._nativeConnection||(cards[name]._nativeConnection={connected:true}),callWS:cards[name]._nativeTransport||(cards[name]._nativeTransport=async m=>{pending++;try{const r=await nativeRPC('ws',{name,message:m});receipts.push(r);refreshCard(name,r.snapshot);if(!r.reply.success)throw r.reply.error;const exact=r.reply.result;if(window.holdA&&name==='A'&&m.service==='get_quality_v1'){holdA=false;heldReply=exact;heldJSON=JSON.stringify(exact);await new Promise(resolve=>{releaseHeld=resolve});if(exact!==heldReply||JSON.stringify(exact)!==heldJSON)throw Error('held reply changed');}return exact;}finally{pending--}}),callService:()=>{throw Error('unexpected legacy transport')}}};
    window.makeCard=(name,s)=>{const c=document.createElement('uninus-nutriculture-card');c.id=name;cards[name]=c;document.body.append(c);c.setConfig({entity:s.status_id,quality_entity:s.quality_id});refreshCard(name,s);};
    makeCard('A',(await nativeRPC('snapshot')).snapshot);
   }''')
   a=p.locator('#A')
   def inspect(): return rpc('inspect')
   def settle(): p.wait_for_function('pending===0 && !Object.values(cards).some(c=>c.qualityOperation)')
   def click(c,k): c.locator('[data-quality-'+k+']').click();settle()
   def checkpoint(case,**kw): rpc('checkpoint',dict(case=case,**kw))
   def field(c,k): return c.locator('[data-quality-field="'+k+'"]')
   def push(result):
    p.evaluate('(s)=>{for(const n of Object.keys(cards))refreshCard(n,s)}',result['snapshot']);settle()
   before=inspect();a.locator('[data-quality-panel] summary').click();p.wait_for_function('!!cards.A.qualityData');settle()
   first=inspect();assert first['options']==before['options'] and first['io']==before['io']
   checkpoint('first_native_GET',dto=p.evaluate('cards.A.qualityData'))
   # All policy controls are filled, including every stage and report confirmation.
   controls=a.locator('[data-quality-panel] input,[data-quality-panel] select').evaluate_all('es=>es.map(e=>({tag:e.tagName,type:e.type,key:e.getAttribute("data-quality-field"),html:e.outerHTML}))')
   checkpoint('actual_policy_controls',controls=controls)
   for k,v in {'stable_samples':2,'stable_interval_seconds':1,'stable_duration_seconds':1,'permit_ttl_seconds':2}.items(): field(a,k).fill(str(v))
   field(a,'enabled').check()
   for k in ['ph','ec','level']:
    field(a,k+'.mode').select_option('reported');field(a,k+'.confirmed').check()
   for s in ['refill','nutrient','acid','mix']: field(a,'required.'+s).check()
   click(a,'save');saved=inspect();assert saved['commit_count']==first['commit_count']+1
   assert saved['io']==first['io']
   assert p.evaluate('!!cards.A.qualityData'), 'FIRST_SAVE_AUTOMATIC_READBACK_REQUIRED'
   assert '已保存並讀回' in a.locator('[data-quality-message]').inner_text()
   assert p.evaluate('cards.A.qualityData.policy_revision')==saved['options']['quality_policy']['revision']
   policy=p.evaluate('cards.A.qualityData.policy');assert policy['enabled'] and all(x['report_contract_confirmed'] for x in policy['sources'].values())
   request=p.evaluate('receipts.find(r=>r.reply.success && r.reply.result?.response?.policy_revision===1)')
   checkpoint('first_native_UI_SAVE_one_commit_zero_IO',policy=policy,options=saved['options'])
   checkpoint('first_Save_automatic_GET_no_manual_refresh',receipts=p.evaluate('receipts'))
   field(a,'stable_samples').fill('3');pre=inspect();push(rpc('dirty_telemetry'));assert field(a,'stable_samples').input_value()=='3'
   assert inspect()['options']==pre['options'];assert inspect()['commit_count']==pre['commit_count'];assert inspect()['io']==pre['io'];click(a,'cancel');assert field(a,'stable_samples').input_value()=='2'
   assert inspect()['options']==pre['options'];assert inspect()['commit_count']==pre['commit_count'];assert inspect()['io']==pre['io'];checkpoint('dirty_telemetry_and_Cancel_no_write')
   full=rpc('multistage_drive');push(full);checkpoint('actual_same_entry_four_stage_completed_OFF_no_leases',native=full)
   grant=rpc('grant');push(grant)
   try:
    p.wait_for_function("cards.A.qualityData?.quality.state==='qualified' && cards.A.shadowRoot.querySelector('[data-quality-truth]').innerText.includes('qualified') && cards.A.shadowRoot.querySelector('[data-quality-permit]').innerText.includes('許可 True')")
   finally:
    checkpoint('grant_convergence_raw_observation',cache=p.evaluate('cards.A.qualityData'),markup=a.locator('[data-quality-panel]').inner_text(),receipts=p.evaluate('receipts'),snapshot=grant['snapshot'])
   assert 'qualified' in a.locator('[data-quality-truth]').inner_text()
   assert 'completed' in a.locator('[data-quality-completion]').inner_text()
   assert '許可 True' in a.locator('[data-quality-permit]').inner_text()
   checkpoint('native_API_sensor_binary_Card_three_truths_grant',dto=grant['dto'],markup=a.locator('[data-quality-panel]').inner_text())
   # Independent passive combined consumer and ordinary standalone readonly consumer.
   p.evaluate('''async()=>{const s=(await nativeRPC('snapshot')).snapshot;makeCard('M',s);const r=document.createElement('uninus-nutriculture-card');r.id='R';cards.R=r;document.body.append(r);r.setConfig({quality_entity:s.quality_id});refreshCard('R',s);}''')
   p.locator('#M [data-quality-panel] summary').click();p.locator('#R [data-quality-panel] summary').click();settle()
   p.wait_for_function("cards.M.qualityData?.permit.granted===true && cards.M.shadowRoot.querySelector('[data-quality-permit]').innerText.includes('許可 True') && cards.R.shadowRoot.querySelector('[data-quality-permit]').innerText.includes('許可 True')")
   assert p.evaluate('JSON.stringify(cards.M.qualityData)===JSON.stringify(cards.M.qualityNative())')
   checkpoint('R4_exact_DTO_expiry_combined_and_standalone_True',api=grant['dto'],cache=p.evaluate('cards.M.qualityData'),native=p.evaluate('cards.M.qualityNative()'),readonly=p.locator('#R [data-quality-panel]').inner_text())
   # New affected live boundary: no transport swap, no GET before native deadline.
   p.evaluate("() => {window.loadedUser=cards.A.hass.user;window.loadedWS=cards.A.hass.callWS;window.loadedConn=cards.A.hass.connection;window.loadedNative=JSON.stringify(cards.A.qualityNative());cards.A.hass.user.is_admin=false;cards.A.hass={...cards.A.hass};}")
   assert p.evaluate("cards.A.hass.user===loadedUser&&cards.A.hass.callWS===loadedWS&&cards.A.hass.connection===loadedConn&&JSON.stringify(cards.A.qualityNative())===loadedNative")
   assert p.evaluate("cards.A.qualityData===null&&cards.A.qualityBaseline===null&&!cards.A.qualitySyncBase&&!cards.A.qualityDirty&&[...cards.A.qualityInputs.values()].every(i=>i.type==='checkbox'?!i.checked:i.value==='')")
   assert '許可 True' not in a.locator('[data-quality-permit]').inner_text()
   p.evaluate("() => {cards.A.hass.user.is_admin=true;cards.A.hass={...cards.A.hass};}")
   assert p.evaluate('cards.A.qualityData===null');assert '許可 True' not in a.locator('[data-quality-permit]').inner_text()
   checkpoint('Q1_loaded_native_True_same_user_same_transport_demotion_purge_regrant_no_cached_True',cache=p.evaluate('cards.A.qualityData'))
   settle();expired=rpc('deadline');push(expired)
   p.wait_for_function("cards.M.qualityData?.permit.granted===false && cards.M.shadowRoot.querySelector('[data-quality-permit]').innerText.includes('不許可 False') && cards.R.shadowRoot.querySelector('[data-quality-permit]').innerText.includes('不許可 False')")
   assert p.evaluate('cards.M.qualityData') == p.evaluate('cards.M.qualityNative()')
   checkpoint('R4_passive_native_callback_combined_and_readonly_False_without_manual_GET',cache=p.evaluate('cards.M.qualityData'),native=p.evaluate('cards.M.qualityNative()'),markup=p.locator('#M [data-quality-panel]').inner_text(),readonly=p.locator('#R [data-quality-panel]').inner_text())
   # New principal must explicitly obtain fresh native management GET, only after timer proved False.
   click(a,'refresh')
   p.wait_for_function("cards.A.qualityData?.permit.granted===false && cards.A.shadowRoot.querySelector('[data-quality-permit]').innerText.includes('不許可 False')")
   assert '許可 True' not in a.locator('[data-quality-permit]').inner_text()
   checkpoint('hard_deadline_callback_no_GET_push_Card_revoke',dto=expired['dto'])
   push(rpc('healthy_no_regrant'));assert '許可 True' not in a.locator('[data-quality-permit]').inner_text();checkpoint('healthy_new_reports_no_regrant')
   p.evaluate('async()=>{makeCard("B",(await nativeRPC("snapshot")).snapshot)}');b=p.locator('#B');b.locator('[data-quality-panel] summary').click();p.wait_for_function('!!cards.B.qualityData');settle();click(a,'refresh')
   field(a,'stable_samples').fill('3');field(b,'stable_samples').fill('4');click(a,'save');pre=inspect();click(b,'save')
   assert inspect()['options']==pre['options'];assert inspect()['commit_count']==pre['commit_count'];assert inspect()['io']==pre['io'];assert inspect()['commit_count']==pre['commit_count'];assert field(b,'stable_samples').input_value()=='4';assert not p.evaluate('receipts.at(-1).reply.success');checkpoint('Card_A_policy_commit_Card_B_stale_quality_CAS_rejected_draft_kept')
   click(b,'refresh');rpc('number_change',12);pre=inspect();field(b,'stable_samples').fill('5');click(b,'save');assert inspect()['options']==pre['options'];assert inspect()['commit_count']==pre['commit_count'];assert inspect()['io']==pre['io'];assert field(b,'stable_samples').input_value()=='5';assert not p.evaluate('receipts.at(-1).reply.success');checkpoint('native_Number_settings_revision_then_stale_Card_quality_Save_rejected')
   click(b,'refresh');field(b,'stable_samples').fill('7');rpc('flow_change');pre=inspect();click(b,'save')
   assert inspect()['options']==pre['options'] and inspect()['commit_count']==pre['commit_count'] and inspect()['io']==pre['io'];assert field(b,'stable_samples').input_value()=='7';assert not p.evaluate('receipts.at(-1).reply.success');checkpoint('native_flow_revision_then_stale_Card_quality_Save_rejected_zero_commit')
   click(a,'refresh');field(a,'stable_samples').fill('6');pre=inspect();rpc('deactivate');click(a,'save');assert inspect()['options']==pre['options'];assert inspect()['commit_count']==pre['commit_count'];assert inspect()['io']==pre['io'];assert not p.evaluate('receipts.at(-1).reply.success');assert field(a,'stable_samples').input_value()=='6';denial=rpc('protected_denial');checkpoint('real_AuthManager_revoked_user_write_denied_target_unread',denial=denial);rpc('reactivate')
   click(a,'refresh');pre=inspect()
   p.evaluate("() => {window.holdA=true;window.heldReply=null;window.releaseHeld=null;window.lateWS=cards.A.hass.callWS;window.lateConn=cards.A.hass.connection;window.lateUser=cards.A.hass.user;}")
   a.locator('[data-quality-refresh]').click();p.wait_for_function('!!window.releaseHeld')
   rpc('deactivate')
   p.evaluate('''async()=>{makeCard('C',(await nativeRPC('snapshot')).snapshot)}''');c=p.locator('#C');c.locator('[data-quality-panel] summary').click();p.wait_for_function('receipts.at(-1)?.reply.success===false')
   denial=rpc('protected_denial');assert 'PRIVATE' not in c.locator('[data-quality-panel]').inner_text();assert not p.evaluate('!!cards.C.qualityData')
   p.evaluate('''() => {cards.A.hass.user.is_admin=false;cards.A.hass={...cards.A._hass};if(cards.A.hass.user!==lateUser||cards.A.hass.callWS!==lateWS||cards.A.hass.connection!==lateConn)throw Error('late fixture transport changed');releaseHeld();}''')
   settle();assert not p.evaluate('!!cards.A.qualityData');assert '許可 True' not in a.locator('[data-quality-permit]').inner_text();assert 'PRIVATE' not in a.locator('[data-quality-panel]').inner_text()
   assert inspect()['options']==pre['options'] and inspect()['commit_count']==pre['commit_count'] and inspect()['io']==pre['io'];checkpoint('held_actual_native_reply_after_real_auth_denial_privacy_owner_fence',denial=denial,sameTransport=p.evaluate('cards.A.hass.callWS===lateWS&&cards.A.hass.connection===lateConn&&cards.A.hass.user===lateUser'),exactReplyUnchanged=p.evaluate('JSON.stringify(heldReply)===heldJSON'),cache=p.evaluate('cards.A.qualityData'));rpc('reactivate')
   fresh=rpc('store_readback');assert fresh['quality']['epoch']!=grant['dto']['epoch'];checkpoint('normal_STOP_fresh_SDK_full_options_policy_numbers_reload_permit_false_new_epoch_count_zero',readback=fresh)
   assert errors==[];rpc('done',{'page_errors':errors,'browser_version':browser.version})
  finally: browser.close()
if __name__=='__main__':
 try: main()
 except BaseException: traceback.print_exc(file=sys.stderr);sys.exit(1)
