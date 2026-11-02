import asyncio
from datetime import timedelta
from homeassistant.util import dt as dt_util
from conftest import entry
from test_writes import ids

async def test_periodic_expiry_and_equal_value_report_recovery(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    status_id = ids(hass,tank)['status']
    now = dt_util.utcnow()
    # Native timestamp parameter, not a fake State object or changed HA class.
    for key in ('ph','ec','level'):
        state = hass.states.get('sensor.'+key)
        hass.states.async_set(state.entity_id,state.state,state.attributes, timestamp=(now-timedelta(seconds=301)).timestamp())
    await asyncio.sleep(5.2)
    await hass.async_block_till_done()
    state = hass.states.get(status_id)
    assert state.state == 'invalid'
    assert state.attributes['reasons'] == ['ph_stale','ec_stale','level_stale']
    ph_before = hass.states.get('sensor.ph').last_updated
    for key in ('ph','ec','level'):
        source = hass.states.get('sensor.'+key)
        hass.states.async_set(source.entity_id,source.state,source.attributes)
    assert hass.states.get('sensor.ph').last_reported > ph_before
    assert hass.states.get('sensor.ph').last_updated == ph_before
    await asyncio.sleep(5.2)
    await hass.async_block_till_done()
    assert hass.states.get(status_id).state == 'within_range'
