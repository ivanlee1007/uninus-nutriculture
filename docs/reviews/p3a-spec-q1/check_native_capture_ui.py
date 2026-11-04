import hashlib,json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path(__file__).parent
JS=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-f1-successor/uninus-nutriculture-card/uninus-nutriculture-card.js')
data=json.loads((OUT/'post-run-master-off.json').read_text())
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe')
 page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content('<html><body></body></html>');page.add_script_tag(path=str(JS))
 page.evaluate('''data=>{window.calls=[];window.card=document.createElement('uninus-nutriculture-card');document.body.append(card);card.setConfig({entity:data.status_id});card.hass={states:data.states,callService:(...args)=>{calls.push(args);return Promise.resolve()}}}''',data)
 result=page.evaluate('''()=>({quality:card.quality.textContent,controls_attached:card.controls.isConnected,master_disabled:card.controlRows.get('automation_enabled').button.disabled,emergency_disabled:card.controlRows.get('emergency_stop').button.disabled,settings_disabled:card.groupApply.disabled,nutrient_stage:card.status().attributes.stage_states.nutrient,flow_state:card.status().state,master_state:card.hass.states[card.status().attributes.control_entities.automation_enabled].state})''')
 page.evaluate("card.invokeControl(card.controlRows.get('automation_enabled'));card.invokeControl(card.controlRows.get('emergency_stop'));card.groupApply.click()")
 result.update(page.evaluate('()=>({calls})'));result.update(browser_version=browser.version,page_errors=errors,shipped_sha256=hashlib.sha256(JS.read_bytes()).hexdigest(),native_capture_sha256=hashlib.sha256((OUT/'post-run-master-off.json').read_bytes()).hexdigest())
 (OUT/'post-run-shipped-ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
 assert not errors
 assert result['controls_attached'], 'Actual native post-run master OFF makes shipped Card reject entire schema3: master ON/reset/emergency/settings inaccessible'
 browser.close()
