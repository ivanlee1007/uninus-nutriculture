"""Exercise native HA flow manager, no flow-framework replacements."""
import pytest
from homeassistant.data_entry_flow import FlowResultType
from conftest import DOMAIN
from test_writes import ids, change

async def test_config_flow_selects_existing_sensors_and_options_rebind(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN,context={'source':'user'})
    assert result['type'] == FlowResultType.FORM
    assert result['step_id'] == 'user'
    result = await hass.config_entries.flow.async_configure(result['flow_id'], {'name':'Tank A','ph':'sensor.ph','ec':'sensor.ec','level':'sensor.level','max_age_seconds':300})
    assert result['type'] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    tank = result['result']
    original = ids(hass,tank)
    await change(hass,original['ph_low'],5.5)
    hass.states.async_set('sensor.alternative_ph',7, {'unit_of_measurement':'pH'})
    options = await hass.config_entries.options.async_init(tank.entry_id)
    assert options['type'] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(options['flow_id'], {'ph':'sensor.alternative_ph','ec':'sensor.ec','level':'sensor.level','max_age_seconds':600})
    assert result['type'] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert ids(hass,tank) == original
    status = hass.states.get(original['status'])
    assert status.state == 'out_of_range'
    assert status.attributes['source_entities']['ph'] == 'sensor.alternative_ph'
    assert status.attributes['parameters']['ph_low'] == 5.5
    hass.states.async_set('sensor.alternative_ph',5.6,{'unit_of_measurement':'pH'})
    await hass.async_block_till_done()
    assert hass.states.get(original['status']).state == 'within_range'
    hass.states.async_set('sensor.ph',9,{'unit_of_measurement':'pH'})
    await hass.async_block_till_done()
    assert hass.states.get(original['status']).state == 'within_range'

@pytest.mark.parametrize('overrides', [{'ph':'sensor.missing'},{'ph':'switch.not_a_sensor'},{'name':' '},{'max_age_seconds':0},{'max_age_seconds':86401},{'max_age_seconds':float('nan')}])
async def test_config_flow_rejects_invalid_binding_or_freshness(hass, overrides):
    result = await hass.config_entries.flow.async_init(DOMAIN,context={'source':'user'})
    assert result['type'] == FlowResultType.FORM
    from homeassistant.data_entry_flow import InvalidData
    payload = {**{'name':'Tank','ph':'sensor.ph','ec':'sensor.ec','level':'sensor.level','max_age_seconds':300},**overrides}
    try:
        result = await hass.config_entries.flow.async_configure(result['flow_id'], payload)
    except InvalidData as err:
        # Core rejects selector schema violations before the integration step.
        assert err.schema_errors
    else:
        assert result['type'] == FlowResultType.FORM
        assert result['errors']
    assert not hass.config_entries.async_entries(DOMAIN)
