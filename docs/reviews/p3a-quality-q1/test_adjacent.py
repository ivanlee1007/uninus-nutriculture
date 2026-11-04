"""Independent reachable neighbor: stage toggles then settled emergency."""
import asyncio,json
from pathlib import Path
import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p3_dosing import dosing_hass,prepared,start_native
from test_p2_control import target,toggle
from test_quality_adjacent_successor import source_bound,capture
pytest_plugins=['p2_fixtures']

async def test_stage_disable_reenable_then_settled_emergency_keeps_truth(dosing_hass):
    hass=dosing_hass
    entry=await prepared(hass,pulse_seconds=2)
    control=entry.runtime_data.control
    stage=control.nutrient_stage
    pump,circ=hass.data['p3_fixture']['outputs']
    source_bound(control)
    try:
        await start_native(hass,entry)
        await asyncio.wait_for(pump.entered_on.wait(),2)
        await toggle(hass,entry,'nutrient_enabled',False)
        await hass.async_block_till_done()
        assert stage.result=='aborted' and not stage.owns_io and not control.running
        assert not pump.is_on and not circ.is_on
        calls=list(hass.data['p3_fixture']['calls'])
        await toggle(hass,entry,'nutrient_enabled',True)
        await toggle(hass,entry,'automation_enabled',False)
        await toggle(hass,entry,'automation_enabled',True)
        await hass.async_block_till_done()
        status=capture(hass,entry,'stage-reenabled-history')
        assert status['state']==status['attributes']['flow_state']=='idle'
        assert status['attributes']['stage_states']['nutrient']=='aborted'
        assert control.run_stage=='nutrient' and stage.result=='aborted'
        assert hass.data['p3_fixture']['calls']==calls
        await hass.services.async_call('button','press',{'entity_id':target(hass,entry,'button','emergency_stop')},blocking=True)
        await hass.async_block_till_done()
        status=capture(hass,entry,'settled-emergency')
        assert status['state']=='fault'
        assert status['attributes']['stage_states']['nutrient']=='fault'
        assert stage.result=='fault' and not stage.owns_io and not control.running
        assert entry.options['control']['fault']=='emergency_stop'
        assert entry.options['control']['automation_enabled'] is False
        assert not pump.is_on and not circ.is_on
        assert all(action=='off' for role,action in hass.data['p3_fixture']['calls'][len(calls):])
        with pytest.raises(ServiceValidationError):
            await toggle(hass,entry,'automation_enabled',True)
        assert entry.options['control']['fault']=='emergency_stop'
        await hass.services.async_call('button','press',{'entity_id':target(hass,entry,'button','reset_fault')},blocking=True)
        await toggle(hass,entry,'nutrient_enabled',False)
        await toggle(hass,entry,'nutrient_enabled',True)
        await hass.async_block_till_done()
        status=capture(hass,entry,'settled-emergency-reset')
        assert status['state']=='disabled' and status['attributes']['fault'] is None
        assert status['attributes']['stage_states']['nutrient']=='fault'
        assert stage.result=='fault' and not control.running and not stage.owns_io
        assert not pump.is_on and not circ.is_on
    finally:
        await control.stop()
