"""Independent historical-outcome replacement at next accepted/pending run."""
import asyncio
import pytest
from test_p3_dosing import dosing_hass,prepared,start_native
from test_p2_control import toggle
from test_quality_adjacent_successor import source_bound,capture
pytest_plugins=['p2_fixtures']

async def test_next_accepted_run_clears_history_until_off_ack_settles(dosing_hass):
 hass=dosing_hass
 entry=await prepared(hass,pulse_seconds=2)
 control=entry.runtime_data.control
 stage=control.nutrient_stage
 source_bound(control)
 pump,circ=hass.data['p3_fixture']['outputs']
 stopper=None
 try:
  await start_native(hass,entry)
  await asyncio.wait_for(pump.entered_on.wait(),2)
  await toggle(hass,entry,'flow_run',False)
  assert stage.result=='aborted' and not stage.owns_io
  await toggle(hass,entry,'automation_enabled',False)
  await toggle(hass,entry,'automation_enabled',True)
  assert stage.result=='aborted' and not pump.is_on and not circ.is_on
  pump.entered_on.clear();pump.entered_off.clear()
  await start_native(hass,entry)
  assert stage.result is None and stage.owns_io and control.running
  await asyncio.wait_for(pump.entered_on.wait(),2)
  pump.off_ack_gate=asyncio.Event()
  stopper=asyncio.create_task(toggle(hass,entry,'flow_run',False))
  await asyncio.wait_for(pump.entered_off.wait(),1)
  control.tank.publish();await asyncio.sleep(0)
  status=capture(hass,entry,'second-run-pending')
  assert not pump.is_on and circ.is_on
  assert stage.result is None and stage.owns_io and control.running
  assert status['attributes']['stage_states']['nutrient']=='stopping'
  pump.off_ack_gate.set();await asyncio.wait_for(stopper,3)
  await toggle(hass,entry,'automation_enabled',False)
  await hass.async_block_till_done()
  status=capture(hass,entry,'second-run-settled')
  assert stage.result=='aborted' and not stage.owns_io and not control.running
  assert status['state']=='disabled' and status['attributes']['stage_states']['nutrient']=='aborted'
  assert not pump.is_on and not circ.is_on
 finally:
  if pump.off_ack_gate:pump.off_ack_gate.set()
  if stopper and not stopper.done():await asyncio.wait_for(stopper,3)
  await control.stop()
