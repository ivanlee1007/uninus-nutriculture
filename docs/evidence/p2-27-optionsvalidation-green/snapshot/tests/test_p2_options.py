"""Native Options control validation; Cancel and latest-merge remain inert."""
import pytest
from homeassistant.data_entry_flow import FlowResultType
from test_p2_control import add_tank, configure, control_hass, option_payload, target, toggle  # noqa: F401


@pytest.mark.parametrize("timeout", [0, 61, float("nan"), True])
async def test_invalid_feedback_setting_rejected_without_partial_save(control_hass, timeout):
    hass = control_hass
    tank = await add_tank(hass)
    before = dict(tank.options)
    from homeassistant.data_entry_flow import InvalidData
    try:
        result = await configure(hass, tank, feedback_timeout=timeout)
    except InvalidData:
        pass  # Native selector schema rejection is a valid denial.
    else:
        assert result["type"] == FlowResultType.FORM
    assert tank.options == before
    assert not hass.data["p2_fixture"]["calls"]


async def test_open_options_preserves_intervening_number_and_switch_changes(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    flow = await hass.config_entries.options.async_init(tank.entry_id)
    await toggle(hass, tank, "automation_enabled")
    await hass.services.async_call("number", "set_value", {"entity_id": target(hass,tank,"number","ph_low"), "value": 5.5}, blocking=True)
    result = await hass.config_entries.options.async_configure(flow["flow_id"], option_payload(hass))
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert tank.options["parameters"]["ph_low"] == 5.5
    assert tank.options["control"]["automation_enabled"] is True
    assert not hass.data["p2_fixture"]["calls"]
    flow = await hass.config_entries.options.async_init(tank.entry_id)
    hass.config_entries.options.async_abort(flow["flow_id"])
    assert not hass.data["p2_fixture"]["calls"]
