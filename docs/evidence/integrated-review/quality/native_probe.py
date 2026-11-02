"""Reviewer-authored additional native boundaries, exact index snapshot."""
import asyncio,json,sys
from pathlib import Path
ROOT=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-index-gate-02/uninus-nutriculture')
sys.path.insert(0,str(ROOT/'tests'))
from conftest import make_hass, entry
from test_writes import ids,change
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import callback

async def main():
 out=Path(__file__).parent
 hass=await make_hass(out/'probe-ha')
 checks={};events=[]
 @callback
 def observe(event): events.append(event.data['domain']+'.'+event.data['service'])
 unsub=hass.bus.async_listen(EVENT_CALL_SERVICE,observe)
 try:
  for key,value,unit in [('ph',5.6,'pH'),('ec',.85,'mS/cm'),('level',2.3,'m')]:
   hass.states.async_set('sensor.'+key,value,{'unit_of_measurement':unit})
  tank=entry();await hass.config_entries.async_add(tank);await hass.async_block_till_done()
  entities=ids(hass,tank)
  # An open stale Options form must preserve a later Number write.
  form=await hass.config_entries.options.async_init(tank.entry_id)
  await change(hass,entities['ph_low'],5.5)
  result=await hass.config_entries.options.async_configure(form['flow_id'],{'ph':'sensor.ph','ec':'sensor.ec','level':'sensor.level','max_age_seconds':600})
  await hass.async_block_till_done()
  assert result['type']==FlowResultType.CREATE_ENTRY
  assert tank.options['parameters']['ph_low']==5.5
  assert tank.options['max_age_seconds']==600
  checks['stale_options_form_preserves_later_number_write']=True
  manager=tank.runtime_data;number=hass.data['number'].get_entity(entities['ec_low'])
  before=dict(tank.options)
  await manager.lock.acquire()
  pending=asyncio.create_task(number.async_set_native_value(.82));await asyncio.sleep(0)
  assert not pending.done();pending.cancel()
  try: await pending
  except asyncio.CancelledError: pass
  else: raise AssertionError('no cancellation')
  assert dict(tank.options)==before
  manager.lock.release()
  await change(hass,entities['ec_low'],.81)
  assert tank.options['parameters']['ec_low']==.81
  checks['cancelled_queued_write_has_no_effect_and_lock_recovers']=True
  # Abort/cancel of a new native options form is nonmutating.
  before=dict(tank.options)
  form=await hass.config_entries.options.async_init(tank.entry_id)
  hass.config_entries.options.async_abort(form['flow_id'])
  await hass.async_block_till_done()
  assert dict(tank.options)==before
  checks['options_abort_is_nonmutating']=True
  assert all(event=='number.set_value' for event in events)
  checks['no_foreign_service_dispatch']=True
  (out/'native-probe-result.json').write_text(json.dumps({'checks':checks,'service_events':events},indent=2))
  print(json.dumps({'checks':checks,'service_events':events},indent=2))
 finally:
  unsub();await hass.async_stop(force=True)
asyncio.run(main())
