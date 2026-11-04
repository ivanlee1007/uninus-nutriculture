"""Independent probes: only fake hardware instance methods are changed."""
import asyncio
import json
from pathlib import Path
import pytest
from test_p3_dosing import dosing_hass, prepared, start_native
from test_p3_dosing_bounds import until
from test_p2_control import target, toggle

pytest_plugins = ['p2_fixtures']
OUT=Path(__file__).parent

@pytest.mark.asyncio
async def test_provider_exception_is_not_persisted_or_published_as_fault(dosing_hass):
    hass=dosing_hass
    entry=await prepared(hass, pulse_seconds=2)
    pump,circ=hass.data['p3_fixture']['outputs']
    # Deliberately fictitious provider diagnostic; no credentials/network.
    payload='REVIEW_SYNTHETIC_PRIVATE_TOKEN=not-a-real-secret; endpoint=http://example.invalid/device; '+('x'*4096)
    async def fail_local_provider(**kwargs):
        pump.entered_on.set()
        raise RuntimeError(payload)
    pump.async_turn_on=fail_local_provider
    control=entry.runtime_data.control
    try:
        receipt=await start_native(hass,entry)
        await asyncio.wait_for(pump.entered_on.wait(),2)
        await until(lambda: control.nutrient_stage.task.done())
        await hass.async_block_till_done()
        status=hass.states.get(target(hass,entry,'sensor','control_status'))
        persisted=entry.options['control']['fault']
        published=status.attributes['fault']
        result={'accepted':receipt['accepted'],'fault_length':len(control.fault),'persisted_equals_provider':persisted==payload,'sensor_equals_provider':published==payload,'all_outputs_off':not pump.is_on and not circ.is_on,'running':control.running,'flow_state':status.state}
        (OUT/'provider-counterexample.json').write_text(json.dumps(result,indent=2))
        print('PROVIDER_COUNTEREXAMPLE',json.dumps(result))
        assert persisted != payload and published != payload, 'Provider diagnostic must not become the persistent/public bounded fault code'
    finally:
        await control.stop()

@pytest.mark.asyncio
async def test_normal_stop_sequence_token_invalid_burst_escalates_all_off(dosing_hass):
    hass=dosing_hass
    entry=await prepared(hass,pulse_seconds=2,sample_mode='sequence',sample_attribute='sample')
    attrs={'unit_of_measurement':'mS/cm','sample':2}
    hass.states.async_set('sensor.ec','0.7',attrs)
    pump,circ=hass.data['p3_fixture']['outputs']
    control=entry.runtime_data.control
    await start_native(hass,entry)
    await asyncio.wait_for(pump.entered_on.wait(),2)
    pump.off_ack_gate=asyncio.Event()
    stopper=asyncio.create_task(toggle(hass,entry,'flow_run',False))
    try:
        await asyncio.wait_for(pump.entered_off.wait(),1)
        assert circ.is_on
        hass.states.async_set('sensor.ec','0.7',{**attrs,'sample':True})
        hass.states.async_set('sensor.ec','0.7',attrs)
        await asyncio.wait_for(circ.entered_off.wait(),0.75)
        assert not pump.off_ack_gate.is_set()
        assert control.fault=='sample_invalid' and not control.master
        print('ADJACENT_STOP_TOKEN_BURST',json.dumps({'fault':control.fault,'circulation_off_while_nutrient_ack_held':not circ.is_on,'running_while_ack_held':control.running}))
    finally:
        pump.off_ack_gate.set()
        await asyncio.wait_for(stopper,2)
        await control.stop()
