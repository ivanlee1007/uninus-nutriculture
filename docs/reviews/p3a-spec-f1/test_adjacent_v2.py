"""Independent adjacent boundary: message-less faults + pending native OFF."""
import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from test_p3_dosing import dosing_hass, prepared, start_native
from test_p3_dosing_bounds import until
from test_p2_control import target, toggle

pytest_plugins = ['p2_fixtures']
OUT=Path(__file__).parent
ROOT=Path('C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-review-f1-successor/uninus-nutriculture')

@pytest.mark.parametrize('error_type',[RuntimeError,Unauthorized])
async def test_message_less_provider_error_latches_while_native_off_ack_pending(dosing_hass,error_type):
    import test_p3_dosing, conftest
    assert Path(test_p3_dosing.__file__).resolve()==(ROOT/'tests/test_p3_dosing.py').resolve()
    assert Path(conftest.__file__).resolve()==(ROOT/'tests/conftest.py').resolve()
    hass=dosing_hass
    entry=await prepared(hass,pulse_seconds=2)
    control=entry.runtime_data.control
    import sys
    module=sys.modules[type(control).__module__]
    assert hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()==hashlib.sha256((ROOT/'custom_components/uninus_nutriculture/control.py').read_bytes()).hexdigest()
    pump,circ=hass.data['p3_fixture']['outputs']
    pump.off_ack_gate=asyncio.Event()
    error=error_type()
    # Core Unauthorized() formats its own name despite no supplied message.
    assert not error.args
    assert str(error) == ('' if error_type is RuntimeError else 'Unauthorized')
    async def fail_provider(**kwargs):
        pump.entered_on.set()
        raise error
    pump.async_turn_on=fail_provider
    try:
        receipt=await start_native(hass,entry)
        assert receipt['accepted']
        await asyncio.wait_for(pump.entered_on.wait(),2)
        await asyncio.wait_for(pump.entered_off.wait(),1)
        await asyncio.wait_for(circ.entered_off.wait(),1)
        assert not pump.off_ack_gate.is_set()
        assert control.fault=='operation_failed'
        assert entry.options['control']['fault']=='operation_failed'
        assert not control.master and control.running
        assert control.nutrient_stage.owns_io and not control.nutrient_stage.task.done()
        assert not pump.is_on and not circ.is_on
        with pytest.raises(ServiceValidationError,match='fault_latched'):
            await toggle(hass,entry,'automation_enabled')
        # Observe actual native Sensor publication, not a helper return.
        entry.runtime_data.publish()
        await asyncio.sleep(0.02)
        status=hass.states.get(target(hass,entry,'sensor','control_status'))
        assert status.attributes['fault']=='operation_failed'
        pending={'fault':control.fault,'master':control.master,'running':control.running,'owns_io':control.nutrient_stage.owns_io,'off_ack_pending':not pump.off_ack_gate.is_set(),'all_outputs_off':not pump.is_on and not circ.is_on,'sensor_fault':status.attributes['fault']}
        pump.off_ack_gate.set()
        await until(lambda:control.nutrient_stage.task.done())
        await hass.async_block_till_done()
        status=hass.states.get(target(hass,entry,'sensor','control_status'))
        assert control.fault=='operation_failed' and not control.running and not control.master
        assert entry.options['control']['fault']=='operation_failed'
        assert entry.options['control']['automation_enabled'] is False
        assert status.state=='fault' and status.attributes['fault']=='operation_failed'
        assert not pump.is_on and not circ.is_on
        assert ('nutrient','off') in hass.data['p3_fixture']['calls']
        assert ('circulation','off') in hass.data['p3_fixture']['calls']
        result={'exception':error_type.__name__,'message':str(error),'pending':pending,'settled':{'fault':control.fault,'flow_state':status.state,'running':control.running,'master':control.master,'all_outputs_off':not pump.is_on and not circ.is_on},'fixture_source':str(test_p3_dosing.__file__),'loaded_control':str(module.__file__)}
        (OUT/('adjacent-'+error_type.__name__+'.json')).write_text(json.dumps(result,indent=2))
        print('ADJACENT_EMPTY_FAULT',json.dumps(result))
    finally:
        pump.off_ack_gate.set()
        await control.stop()
