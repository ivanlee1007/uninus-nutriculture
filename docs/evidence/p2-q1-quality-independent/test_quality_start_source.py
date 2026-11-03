import asyncio
import json
import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, configure, toggle

@pytest.mark.parametrize('recover', [False, True])
async def test_invalid_source_during_applied_on_cannot_be_forgotten(control_hass, recover):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=2)
    await toggle(hass, tank, 'automation_enabled')
    await toggle(hass, tank, 'refill_enabled')
    hardware = hass.data['p2_fixture']['hardware']
    hardware.on_entered, hardware.on_release = asyncio.Event(), asyncio.Event()
    start = asyncio.create_task(toggle(hass, tank, 'flow_run'))
    await asyncio.wait_for(hardware.on_entered.wait(), 2)
    # Simulate a real provider that has applied ON but is awaiting its API return.
    hardware._attr_is_on = True
    hardware.async_write_ha_state()
    await asyncio.sleep(0.05)
    hass.states.async_set('sensor.ph', 'unavailable')
    await asyncio.sleep(0.10)  # Allow the production event/evaluate tasks to run.
    observed = {'recover': recover, 'during_invalid': {
        'state': tank.runtime_data.control.flow_state,
        'fault': tank.runtime_data.control.fault,
        'output': hass.states.get(hardware.entity_id).state,
        'calls': [c[0] for c in hass.data['p2_fixture']['calls']]}}
    if recover:
        hass.states.async_set('sensor.ph', 5.6, {'unit_of_measurement': 'pH'})
        await asyncio.sleep(0.05)
    hardware.on_release.set()
    result = (await asyncio.gather(start, return_exceptions=True))[0]
    await hass.async_block_till_done()
    observed['after_return'] = {
        'result': type(result).__name__,
        'state': tank.runtime_data.control.flow_state,
        'fault': tank.runtime_data.control.fault,
        'output': hass.states.get(hardware.entity_id).state,
        'calls': [c[0] for c in hass.data['p2_fixture']['calls']]}
    print('OBSERVATION=' + json.dumps(observed))
    try:
        assert isinstance(result, ServiceValidationError), 'Observed necessary-source invalidation must revoke this already-admitted ON, even if source recovers before provider returns'
        assert hass.states.get(hardware.entity_id).state == 'off'
        assert tank.runtime_data.control.fault is not None
    finally:
        await toggle(hass, tank, 'flow_run', False)
