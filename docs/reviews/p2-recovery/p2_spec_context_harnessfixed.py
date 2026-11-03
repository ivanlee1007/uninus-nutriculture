import os, sys, asyncio, json
from pathlib import Path
os.environ['TMPDIR'] = 'C:/Users/ivanl/.hermes/cache/scratch'
sys.dont_write_bytecode = True
sys.path.insert(0, 'D:/UNiNUS Projects/AI project/uninus-nutriculture/tests')
from p2_fixtures import control_hass
from test_p2_acceptance import ready
from test_p2_control import target
from homeassistant.auth import auth_manager_from_config
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError

async def main():
    gen = control_hass.__wrapped__(Path('C:/Users/ivanl/.hermes/cache/scratch/p2-spec-independent-native-parent-harnessfix'))
    hass = await anext(gen)
    try:
        tank = await ready(hass)
        hass.auth = await auth_manager_from_config(hass, [], [])
        owner = await hass.auth.async_create_user('owner')
        admin = await hass.auth.async_create_user('admin', group_ids=['system-admin'])
        outsider = await hass.auth.async_create_user('non-admin')
        entity = target(hass, tank, 'switch', 'flow_run')
        async def call(service, context):
            await hass.services.async_call('switch', service, {'entity_id': entity}, blocking=True, context=context)
        before = len(hass.data['p2_fixture']['calls'])
        try:
            await call('turn_on', Context(user_id=outsider.id))
        except HomeAssistantError:
            pass
        else:
            raise AssertionError('non-admin start accepted')
        assert len(hass.data['p2_fixture']['calls']) == before
        first = Context(user_id=admin.id)
        stop = Context(user_id=owner.id)
        await call('turn_on', first)
        await call('turn_off', stop)
        assert hass.data['p2_fixture']['calls'][-1][2].parent_id == stop.id
        second = Context(user_id=admin.id)
        await call('turn_on', second)
        await hass.auth.async_remove_user(admin)
        level = hass.states.get(tank.runtime_data.sources['level'])
        hass.states.async_set(level.entity_id, tank.runtime_data.control.high_bound, dict(level.attributes))
        await hass.async_block_till_done()
        off = hass.data['p2_fixture']['calls'][-1]
        assert off[0] == 'turn_off'
        assert off[2].user_id is None
        assert off[2].parent_id == second.id
        assert off[2].parent_id != stop.id
        assert hass.states.get(hass.data['p2_fixture']['hardware'].entity_id).state == 'off'
        assert not tank.runtime_data.control.running
        print('INDEPENDENT_RESULT=' + json.dumps({'non_admin_start_denied':True, 'deleted_user_high_water_off':True, 'new_run_origin':second.id, 'previous_stop_origin':stop.id, 'off_parent':off[2].parent_id, 'stale_context_not_reused':True}))
    finally:
        await gen.aclose()

asyncio.run(main())
