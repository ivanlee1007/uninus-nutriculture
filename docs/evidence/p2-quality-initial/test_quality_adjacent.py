import asyncio
from test_p2_control import add_tank, configure, toggle

async def test_same_transient_source_invalid_after_start_is_latched(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=2)
    await toggle(hass, tank, 'automation_enabled')
    await toggle(hass, tank, 'refill_enabled')
    await toggle(hass, tank, 'flow_run')
    hardware = hass.data['p2_fixture']['hardware']
    hass.states.async_set('sensor.ph', 'unavailable')
    await asyncio.sleep(0.1)
    hass.states.async_set('sensor.ph', 5.6, {'unit_of_measurement': 'pH'})
    await hass.async_block_till_done()
    print('ADJACENT', tank.runtime_data.control.flow_state, tank.runtime_data.control.fault, hass.states.get(hardware.entity_id).state)
    assert tank.runtime_data.control.fault == 'source_invalid'
    assert not tank.runtime_data.control.running
    assert hass.states.get(hardware.entity_id).state == 'off'
