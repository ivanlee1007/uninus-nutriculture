"""Reviewer-owned shipped-browser -> real isolated HA ServiceRegistry probe."""
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path('D:/UNiNUS Projects/AI project')
OUT = Path(__file__).resolve().parent
BACK = ROOT / 'uninus-nutriculture'
CARD = ROOT / 'uninus-nutriculture-card'
sys.path.insert(0, str(BACK / 'tests'))
import homeassistant  # initialize native schema before fixtures
from conftest import make_hass
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
def json_dumps(value):
    return json.dumps(value, default=dict, ensure_ascii=False)
sys.path.append(str(CARD / '.venv/Lib/site-packages'))
from playwright.async_api import async_playwright

async def main():
    import importlib.metadata
    evidence = {'core': importlib.metadata.version('homeassistant'), 'calls': [], 'checks': {}}
    hass = await make_hass(OUT / 'ha')
    browser = None
    try:
        @callback
        def observe(event):
            evidence['calls'].append(dict(event.data))
        hass.bus.async_listen(EVENT_CALL_SERVICE, observe)
        for key,value,unit in [('ph',5.6,'pH'),('ec',.85,'mS/cm'),('level',2.3,'m')]:
            hass.states.async_set('sensor.'+key, value, {'unit_of_measurement':unit})
        flow = await hass.config_entries.flow.async_init('uninus_nutriculture',context={'source':'user'})
        created = await hass.config_entries.flow.async_configure(flow['flow_id'], {'name':'Reviewer tank','ph':'sensor.ph','ec':'sensor.ec','level':'sensor.level','max_age_seconds':300})
        entry = created['result']
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        ids = {row.unique_id.split(':')[-1]:row.entity_id for row in er.async_entries_for_config_entry(registry,entry.entry_id)}
        status_id = ids['status']
        def snapshot():
            return json.loads(json_dumps({s.entity_id:{'state':s.state,'attributes':dict(s.attributes)} for s in hass.states.async_all()}))
        async def service(args):
            domain,name,data = args
            evidence.setdefault('card_payloads',[]).append(args)
            try:
                await hass.services.async_call(domain,name,data,blocking=True)
                await hass.async_block_till_done()
                return {'ok':True,'states':snapshot()}
            except Exception as err:
                return {'ok':False,'error':str(err),'states':snapshot()}
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, executable_path='C:/Users/ivanl/AppData/Local/ms-playwright/chromium-1248/chrome-win64/chrome.exe')
            page = await browser.new_page()
            await page.expose_function('nativeService', service)
            await page.set_content('<!doctype html><html><body></body></html>')
            await page.add_script_tag(path=str(CARD/'uninus-nutriculture-card.js'))
            await page.evaluate('''({states,entity})=>{
                window.card=document.createElement('uninus-nutriculture-card');document.body.append(card);
                window.h={states,callService:async(...args)=>{const result=await nativeService(args);h.states=result.states;card.hass=h;if(!result.ok)throw new Error(result.error);}};
                card.setConfig({entity});card.hass=h;card.details.open=true;
            }''', {'states':snapshot(),'entity':status_id})
            async def save(key,value):
                row = page.locator('[data-param="'+key+'"]')
                await row.locator('input').fill(str(value))
                assert await row.locator('button').is_enabled()
                await row.locator('button').click()
                await page.wait_for_function('(key)=>!card.rows.get(key).pending',arg=key)
                return await row.inner_text()
            # Real advertised pH step .1, not permissive browser fixture .01.
            row=page.locator('[data-param="ph_low"]')
            assert await row.locator('input').get_attribute('step') == '0.1'
            await row.locator('input').fill('5.55')
            assert await row.locator('button').is_disabled()
            assert not evidence.get('card_payloads')
            evidence['checks']['actual_step_blocks_5_55']=True
            await save('ph_low',5.5)
            assert entry.options['parameters']['ph_low']==5.5
            assert hass.states.get(status_id).attributes['parameters']['ph_low']==5.5
            assert hass.states.get(status_id).state=='within_range'
            evidence['checks']['native_success_and_status_readback']=True
            before=dict(entry.options['parameters'])
            message=await save('ph_low',5.9)
            assert '儲存失敗' in message
            assert await row.locator('input').input_value()=='5.9'
            assert dict(entry.options['parameters'])==before
            evidence['checks']['native_pair_rejection_preserves_draft_options']=True
            values={'level_low':2.26,'level_high':2.41,'ph_low':5.4,'ph_high':5.9,'ec_low':.81,'ec_high':.91,'refill_timeout':191,'ec_timeout':91,'ph_timeout':191,'mix_duration':11}
            for key,value in values.items():
                await save(key,value)
                assert entry.options['parameters'][key]==value
            assert dict(hass.states.get(status_id).attributes['parameters'])==values
            evidence['checks']['all_ten_real_service_writes']=True
            await save('ph_high',5.5)
            assert hass.states.get(status_id).state=='out_of_range'
            await save('ph_high',5.9)
            assert hass.states.get(status_id).state=='within_range'
            evidence['checks']['quality_recomputed_both_directions']=True
            registry.async_update_entity(ids['ec_low'], new_entity_id='number.reviewer_renamed_ec')
            await hass.async_block_till_done()
            await page.evaluate('(states)=>{h.states=states;card.hass=h}',snapshot())
            await save('ec_low',.82)
            assert evidence['card_payloads'][-1][2]['entity_id']=='number.reviewer_renamed_ec'
            evidence['checks']['registry_rename_real_target']=True
            # Do not alter entity class or registry: inject native unavailable state.
            target=ids['ph_low']; old=hass.states.get(target)
            hass.states.async_set(target,'unavailable',dict(old.attributes))
            await hass.async_block_till_done()
            published=dict(hass.states.get(status_id).attributes['parameter_entities'])
            evidence['unavailable_target_map']=published
            evidence['checks']['unavailable_number_omitted']= 'ph_low' not in published
            await page.evaluate('(states)=>{h.states=states;card.hass=h}',snapshot())
            assert await row.locator('button').is_disabled()
            evidence['checks']['card_blocks_unavailable_number']=True
            assert all(c['domain']=='number' and c['service']=='set_value' for c in evidence['calls'])
            assert hass.states.get(status_id).attributes['ready_for_irrigation'] is False
            evidence['checks']['no_output_services_shadow_only']=True
            evidence['final_status']={'state':hass.states.get(status_id).state,'attributes':dict(hass.states.get(status_id).attributes)}
            await browser.close();browser=None
    finally:
        if browser: await browser.close()
        await hass.async_stop(force=True)
        (OUT/'bridge-result.json').write_text(json_dumps(evidence),encoding='utf-8')
    print(json.dumps({'checks':evidence['checks'],'card_payload_count':len(evidence['card_payloads']),'service_event_count':len(evidence['calls'])},indent=2))

asyncio.run(main())
