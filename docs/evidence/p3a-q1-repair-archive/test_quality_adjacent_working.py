"""Independent native post-run projection and cleanup-adjacent probes."""
import asyncio,json,hashlib,sys
from pathlib import Path
import pytest
from test_p3_dosing import dosing_hass,prepared,start_native
from test_p3_dosing_bounds import until
from test_p2_control import target,toggle
pytest_plugins=['p2_fixtures']
OUT=Path(__file__).parent
ROOT=Path('D:\\UNiNUS Projects\\AI project\\uninus-nutriculture')

def source_bound(control):
 import conftest,test_p3_dosing
 assert Path(conftest.__file__).resolve()==(ROOT/'tests/conftest.py').resolve()
 assert Path(test_p3_dosing.__file__).resolve()==(ROOT/'tests/test_p3_dosing.py').resolve()
 for name in ['control','nutrient','sensor']:
  mod=sys.modules['custom_components.uninus_nutriculture.'+name]
  assert hashlib.sha256(Path(mod.__file__).read_bytes()).digest()==hashlib.sha256((ROOT/('custom_components/uninus_nutriculture/'+name+'.py')).read_bytes()).digest()

def capture(hass,entry,label):
 control=entry.runtime_data.control
 status_id=target(hass,entry,'sensor','control_status')
 states={s.entity_id:{'state':s.state,'attributes':dict(s.attributes)} for s in hass.states.async_all()}
 data={'status_id':status_id,'states':states,'persisted_control':dict(entry.options['control']),'flow_state':control.flow_state,'running':control.running,'owns_io':control.nutrient_stage.owns_io,'outputs':{o.role:o.is_on for o in hass.data['p3_fixture']['outputs']},'calls':hass.data['p3_fixture']['calls']}
 (OUT/(label+'.json')).write_text(json.dumps(data,indent=2,default=str))
 print(label,json.dumps({k:v for k,v in data.items() if k!='states'}))
 return states[status_id]

async def test_post_run_master_off_keeps_shipped_schema3_reoperable(dosing_hass):
 hass=dosing_hass;entry=await prepared(hass,pulse_seconds=2);control=entry.runtime_data.control
 source_bound(control)
 pump,circ=hass.data['p3_fixture']['outputs']
 try:
  await start_native(hass,entry)
  await asyncio.wait_for(pump.entered_on.wait(),2)
  await toggle(hass,entry,'flow_run',False)
  assert control.flow_state=='aborted'
  await toggle(hass,entry,'automation_enabled',False)
  await hass.async_block_till_done()
  status=capture(hass,entry,'post-run-master-off')
  assert entry.options['control']['automation_enabled'] is False
  assert not control.running and not pump.is_on and not circ.is_on
  legal={'unsupported','idle','starting','waiting_resource','running','stopping','completed','aborted','fault','skipped_disabled','skipped_weekday','blocked_dependency'}
  assert status['attributes']['stage_states']['nutrient'] in legal, 'Real native post-run schema3 is rejected by shipped validV3; Card cannot re-enable master'
 finally:
  await control.stop()

async def test_timestamp_invalid_recovery_during_normal_off_pending_latches(dosing_hass):
 from datetime import timedelta
 from homeassistant.util import dt as dt_util
 hass=dosing_hass;entry=await prepared(hass,pulse_seconds=2,sample_mode='timestamp',sample_attribute='sample');control=entry.runtime_data.control
 source_bound(control)
 attrs={'unit_of_measurement':'mS/cm','sample':dt_util.utcnow().isoformat()}
 hass.states.async_set('sensor.ec','0.70',attrs)
 pump,circ=hass.data['p3_fixture']['outputs']
 await start_native(hass,entry)
 await asyncio.wait_for(pump.entered_on.wait(),2)
 pump.off_ack_gate=asyncio.Event()
 stopper=asyncio.create_task(toggle(hass,entry,'flow_run',False))
 try:
  await asyncio.wait_for(pump.entered_off.wait(),1)
  assert circ.is_on
  hass.states.async_set('sensor.ec','0.70',{**attrs,'sample':(dt_util.utcnow()+timedelta(days=1)).isoformat()})
  hass.states.async_set('sensor.ec','0.70',attrs)
  await asyncio.wait_for(circ.entered_off.wait(),0.75)
  assert not pump.off_ack_gate.is_set() and control.running
  assert entry.options['control']['fault']=='sample_invalid'
  assert entry.options['control']['automation_enabled'] is False
  capture(hass,entry,'timestamp-cleanup-pending')
 finally:
  pump.off_ack_gate.set()
  await asyncio.wait_for(stopper,2)
  await control.stop()
 await hass.async_block_till_done()
 status=capture(hass,entry,'timestamp-cleanup-settled')
 assert not control.running and not pump.is_on and not circ.is_on
 assert status['attributes']['fault']=='sample_invalid'
