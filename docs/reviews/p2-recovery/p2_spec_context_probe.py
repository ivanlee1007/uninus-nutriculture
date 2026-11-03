import os, sys, asyncio, json
from pathlib import Path
os.environ['TMPDIR'] = 'C:/Users/ivanl/.hermes/cache/scratch'
sys.dont_write_bytecode = True
sys.path.insert(0, 'D:/UNiNUS Projects/AI project/uninus-nutriculture/tests')
from p2_fixtures import control_hass
from test_p2_control import add_tank, configure, toggle, target
from homeassistant.auth import auth_manager_from_config
from homeassistant.core import Context

async def main():
    root = Path('C:/Users/ivanl/.hermes/cache/scratch/p2-spec-native-context')
    gen = control_hass.__wrapped__(root)
    hass = await anext(gen)
    try:
        tank = await add_tank(hass)
        await configure(hass, tank)
        await toggle(hass, tank, 'automation_enabled')
        await toggle(hass, tank, 'refill_enabled')
        hass.auth = await auth_manager_from_config(hass, [], [])
        owner = await hass.auth.async_create_user('owner')
        ctx = Context(user_id=owner.id)
        for service in ('turn_on', 'turn_off'):
            await hass.services.async_call('switch', service, {'entity_id': target(hass, tank, 'switch', 'flow_run')}, blocking=True, context=ctx)
        result = {'input_context': {'id':ctx.id,'user_id':owner.id}, 'output_calls': [{'service':s,'id':c.id,'user_id':c.user_id,'parent_id':c.parent_id} for s,d,c in hass.data['p2_fixture']['calls']]}
        print('SPEC_CONTEXT_RESULT='+json.dumps(result))
        assert result['output_calls'][0]['user_id'] == owner.id
        assert result['output_calls'][1]['user_id'] is None
    finally:
        await gen.aclose()

asyncio.run(main())
