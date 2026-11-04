import json,sys,os,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
TOOLS=Path(__file__).resolve().parent
ROOT=TOOLS.parent
OUT=Path(os.environ['P3C_JOIN_OUTPUT']).resolve()
OUT.mkdir(parents=True,exist_ok=True)
counter=0
def rpc(kind,payload=None):
 global counter
 counter+=1
 print(json.dumps({'id':counter,'kind':kind,'payload':payload}),flush=True)
 line=sys.stdin.readline()
 if not line: raise RuntimeError('parent EOF')
 r=json.loads(line)
 if r.get('harness_error'): raise RuntimeError(r['harness_error'])
 return r

def main():
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_EXECUTABLE'))
  page=browser.new_page(viewport={'width':768,'height':1100})
  page.set_default_timeout(10000)
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content('<!doctype html><meta charset="utf-8"><body>')
  page.evaluate("console.log=console.info=console.warn=()=>{}")
  page.expose_function('nativeRPC',rpc)
  page.add_script_tag(path=str(ROOT.parent/'uninus-nutriculture-card/uninus-nutriculture-card.js'))
  page.evaluate('''async()=>{
   await customElements.whenDefined('uninus-nutriculture-card');
   window.cards={};window.receipts=[];window.pending=0;
   window.refreshCard=(name,s)=>{const c=cards[name];c.hass={states:s.states,user:{id:s.user_id,is_admin:true},connection:{connected:true},callWS:async m=>{
     pending++;try{const r=await nativeRPC('ws',{name,message:m});receipts.push(r);refreshCard(name,r.snapshot);if(!r.reply.success)throw r.reply.error;return r.reply.result;}finally{pending--}
   },callService:async(domain,service,data)=>{pending++;try{const r=await nativeRPC('ws',{name,message:{type:'call_service',domain,service,service_data:data}});receipts.push(r);refreshCard(name,r.snapshot);if(!r.reply.success)throw r.reply.error;return r.reply.result;}finally{pending--}}};};
   window.makeCard=async(name,s)=>{const c=document.createElement('uninus-nutriculture-card');c.id=name;cards[name]=c;document.body.append(c);c.setConfig({entity:s.status_id});refreshCard(name,s);};
   const r=await nativeRPC('snapshot');window.initial=r.snapshot;await makeCard('A',initial);
  }''')
  a=page.locator('#A')
  assert a.locator('[data-flow-row]').count()==4
  rpc('checkpoint',{'case':'first_callable_join','browser':browser.version,'rows':4})
  def settle(): page.wait_for_function('pending===0')
  def typed(sel,value):
   loc=a.locator(sel);loc.click();loc.press('ControlOrMeta+A');loc.press_sequentially(value,delay=25)
  before=rpc('inspect')
  a.locator('[data-plan-cancel]').click()
  assert rpc('inspect')['options']==before['options']
  a.locator('[data-flow-row="acid"] [data-move="up"]').click()
  a.locator('[data-flow-row="acid"] [data-flow-field="start_rule"]').select_option('after_previous_started')
  typed('[data-flow-row="acid"] [data-flow-field="delay_seconds"]','2')
  typed('[data-flow-row="acid"] [data-flow-field="wait_timeout_seconds"]','25')
  rpc('checkpoint',{'case':'editor_dom','html':a.locator('[data-flow-row="acid"]').inner_html()})
  # Only trusted control events; determine condition selectors from shipped DOM.
  cond=a.locator('[data-flow-row="acid"] [data-flow-field="source"]')
  if cond.count():
   cond.select_option('level')
   a.locator('[data-flow-row="acid"] [data-flow-field="operator"]').select_option('gte')
   typed('[data-flow-row="acid"] [data-flow-field="value"]','0.5')
  a.locator('[data-flow-row="mix"] [data-flow-day="sun"]').uncheck()
  timeout=a.locator('[data-run-timeout]')
  if timeout.count(): timeout.fill('130')
  page.evaluate('cards.A.details.open=true;cards.A.doseDetails.open=true')
  typed('[data-acid="pulse_seconds"] input','1')
  a.locator('[data-plan-preview]').click();settle()
  assert a.locator('[data-preview-day]').count()==7
  assert rpc('inspect')['options']==before['options']
  assert rpc('inspect')['io']==before['io']
  a.locator('[data-plan-apply]').click();settle()
  page.wait_for_function("cards.A.planMessage.textContent.includes('已套用')")
  saved=rpc('inspect')
  assert a.locator('[data-acid="pulse_seconds"] input').input_value()=='1'
  assert a.locator('[data-group-apply]').is_disabled()
  a.locator('[data-group-cancel]').click()
  typed('[data-flow-row="mix"] [data-flow-field="delay_seconds"]','6')
  typed('[data-acid="pulse_seconds"] input','1')
  a.locator('[data-group-apply]').click();settle()
  page.wait_for_function("cards.A.groupMessage.textContent.includes('已套用')")
  numeric=rpc('inspect')
  assert numeric['options']['flow_plan']==saved['options']['flow_plan']
  assert numeric['options']['flow_plan_revision']==saved['options']['flow_plan_revision']
  assert numeric['options']['acid_parameters']['pulse_seconds']==1
  assert a.locator('[data-flow-row="mix"] [data-flow-field="delay_seconds"]').input_value()=='6'
  assert a.locator('[data-plan-apply]').is_disabled()
  rpc('checkpoint',{'case':'independent_settings7_plan5_namespaces'})
  assert saved['options']['settings_revision']==before['options']['settings_revision']+1
  assert saved['options']['flow_plan_revision']==before['options']['flow_plan_revision']+1
  assert saved['io']==before['io']
  page.evaluate("async()=>{cards.A.remove();await makeCard('A',(await nativeRPC('snapshot')).snapshot)}")
  a=page.locator('#A')
  assert a.locator('[data-flow-row="acid"] [data-flow-field="delay_seconds"]').input_value()=='2'
  rpc('checkpoint',{'case':'preview_apply_fresh_reopen','settings_revision':saved['options']['settings_revision'],'flow_plan_revision':saved['options']['flow_plan_revision']})
  # Dirty drafts share a frozen native snapshot. B's reply refreshes B only.
  page.evaluate("async()=>{await makeCard('B',(await nativeRPC('snapshot')).snapshot)}")
  b=page.locator('#B')
  typed('[data-flow-row="acid"] [data-flow-field="delay_seconds"]','3')
  b.locator('[data-flow-row="acid"] [data-flow-field="delay_seconds"]').fill('4')
  b.locator('[data-plan-apply]').click();settle()
  racebefore=rpc('inspect')
  assert a.locator('[data-plan-apply]').is_enabled()
  a.locator('[data-plan-apply]').click();settle()
  raceafter=rpc('inspect')
  assert raceafter['options']==racebefore['options'] and raceafter['io']==racebefore['io']
  assert a.locator('[data-flow-row="acid"] [data-flow-field="delay_seconds"]').input_value()=='3'
  assert 'settings_conflict' in a.locator('[data-plan-message]').inner_text()
  rpc('checkpoint',{'case':'native_two_card_CAS','last':page.evaluate('receipts.at(-1).reply')})
  a.locator('[data-plan-cancel]').click()
  typed('[data-flow-row="acid"] [data-flow-field="delay_seconds"]','5')
  authbefore=rpc('inspect');rpc('deactivate')
  a.locator('[data-plan-apply]').click();settle()
  authafter=rpc('inspect')
  assert authbefore['options']==authafter['options'] and authbefore['io']==authafter['io']
  assert page.evaluate('receipts.at(-1).reply.success') is False
  rpc('checkpoint',{'case':'native_inactive_denial','last':page.evaluate('receipts.at(-1).reply')})
  rpc('reactivate')
  stored=rpc('store_readback')
  assert stored['options']==authafter['options']
  rpc('checkpoint',{'case':'fresh_native_Store_readback','store_key':stored['store_key']})
  for entrance in ('service','switch'):
   r=rpc('terminal',entrance)
   page.evaluate('(s)=>{cards.A.setConfig({entity:s.status_id});refreshCard("A",s)}',r['snapshot'])
   assert a.locator('[data-flow-row]').count()==4
   assert a.locator('[data-plan-preview]').is_enabled()
   text=a.locator('[data-flow-editor]').inner_text()
   assert text.count('result: completed')==4,text
   physical=page.evaluate('cards.A.unsupported.textContent')
   assert all(k+' off' in physical for k in ('refill','nutrient','acid','circulation')),physical
   rpc('checkpoint',{'case':'native_terminal_consumed','entrance':entrance,'text':text,'physical':physical})
  prepared=rpc('multistage_prepare')
  page.evaluate('(s)=>{cards.A.setConfig({entity:s.status_id});refreshCard("A",s)}',prepared['snapshot'])
  page.evaluate('cards.A.controls.dataset.ownedControls=""')
  # Click the actual registered flow_run button, not invokeControl directly.
  button=page.evaluate_handle('cards.A.controlRows.get("flow_run").button')
  button.as_element().click();settle()
  assert page.evaluate('receipts.at(-1).reply.success')
  r=rpc('multistage_drive')
  page.evaluate('(s)=>refreshCard("A",s)',r['snapshot'])
  runtime=a.locator('[data-flow-editor]').inner_text()
  assert runtime.count('result: completed')==4,runtime
  assert all(k+' off' in page.evaluate('cards.A.unsupported.textContent') for k in ('refill','nutrient','acid','circulation'))
  rpc('checkpoint',{'case':'card_flow_run_real_four_stage','runtime':runtime,'io':r['io']})
  assert not errors,errors
  page.screenshot(path=str(OUT/'final-browser.png'),full_page=True)
  rpc('done',{'page_errors':errors})
  browser.close()
if __name__=='__main__':
 try: main()
 except Exception:
  traceback.print_exc(file=sys.stderr);sys.exit(1)
