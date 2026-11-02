import asyncio
import pytest
from homeassistant.exceptions import HomeAssistantError
from conftest import entry
from test_writes import change, ids

@pytest.mark.parametrize(('key','value'), [('ph_low',5.8),('ec_high',0.8),('level_low',2.4),('ph_low',5.45),('refill_timeout',1.5),('mix_duration',0),('ec_low',float('nan')),('level_low',float('inf')),('ph_high',-1)])
async def test_invalid_native_write_is_atomic(hass, key, value):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    entities = ids(hass, tank)
    before = dict(hass.states.get(entities['status']).attributes['parameters'])
    options = dict(tank.options)
    with pytest.raises((HomeAssistantError, ValueError)):
        await change(hass, entities[key], value)
    assert dict(tank.options) == options
    assert dict(hass.states.get(entities['status']).attributes['parameters']) == before
    for key, expected in before.items():
        assert float(hass.states.get(entities[key]).state) == expected

async def test_concurrent_conflicting_writes_keep_valid_pair(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    entities = ids(hass, tank)
    results = await asyncio.gather(change(hass,entities['ph_low'],5.7), change(hass,entities['ph_high'],5.5), return_exceptions=True)
    assert sum(isinstance(x,HomeAssistantError) for x in results) == 1
    params = hass.states.get(entities['status']).attributes['parameters']
    assert params['ph_low'] < params['ph_high']
    assert dict(params) == tank.options['parameters']
