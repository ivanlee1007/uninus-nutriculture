"""Entry lifecycle, exact identity and multi-tank isolation."""
import asyncio
import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from conftest import entry
from test_writes import ids, change

async def test_unloaded_and_queued_writes_rejected(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    entities = ids(hass,tank)
    manager = tank.runtime_data
    entity = hass.data['number'].get_entity(entities['ph_low'])
    before = dict(tank.options)
    await manager.lock.acquire()
    queued = asyncio.create_task(entity.async_set_native_value(5.5))
    await asyncio.sleep(0)
    assert not queued.done()
    assert await hass.config_entries.async_unload(tank.entry_id)
    manager.lock.release()
    with pytest.raises(HomeAssistantError):
        await queued
    with pytest.raises(HomeAssistantError):
        await entity.async_set_native_value(5.5)
    assert tank.options == before
    assert not manager.listeners
    # Core keeps a registry-owned unavailable placeholder after platform unload.
    unloaded_state = hass.states.get(entities['status'])
    assert unloaded_state is None or unloaded_state.state == 'unavailable'
    hass.states.async_set('sensor.ph',9,{'unit_of_measurement':'pH'})
    await asyncio.sleep(5.2)
    await hass.async_block_till_done()
    # Core keeps a registry-owned unavailable placeholder after platform unload.
    unloaded_state = hass.states.get(entities['status'])
    assert unloaded_state is None or unloaded_state.state == 'unavailable'

async def test_registry_targets_follow_rename_disable_delete(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    entities = ids(hass,tank)
    registry = er.async_get(hass)
    registry.async_update_entity(entities['ph_low'],new_entity_id='number.my_ph_limit')
    await hass.async_block_till_done()
    status = hass.states.get(entities['status'])
    assert status.attributes['parameter_entities']['ph_low'] == 'number.my_ph_limit'
    await change(hass,'number.my_ph_limit',5.5)
    registry.async_update_entity(entities['ec_low'], disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done()
    assert 'ec_low' not in hass.states.get(entities['status']).attributes['parameter_entities']
    registry.async_remove(entities['level_low'])
    await hass.async_block_till_done()
    assert 'level_low' not in hass.states.get(entities['status']).attributes['parameter_entities']
    assert len(hass.states.get(entities['status']).attributes['parameter_entities']) == 8

async def test_two_same_name_tanks_are_isolated_and_reload_stable(hass):
    first, second = entry(),entry()
    for tank in (first,second):
        await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    one,two = ids(hass,first),ids(hass,second)
    assert set(one.values()).isdisjoint(two.values())
    await change(hass,one['ec_low'],0.81)
    assert float(hass.states.get(two['ec_low']).state) == 0.8
    assert await hass.config_entries.async_reload(first.entry_id)
    await hass.async_block_till_done()
    assert ids(hass,first) == one
    assert float(hass.states.get(one['ec_low']).state) == 0.81
    assert hass.states.get(two['status']).attributes['parameters']['ec_low'] == 0.8
