"""Real native Options Save, Cancel and reopen acceptance."""

import pytest
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from p3_fixtures import DOSING, commission
from p3_fixtures import nutrient_hass as nutrient_hass
from test_p2_control import add_tank


async def test_native_save_cancel_reopen(nutrient_hass):
    hass = nutrient_hass
    entry = await add_tank(hass)
    before = dict(entry.options)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    hass.config_entries.options.async_abort(flow["flow_id"])
    assert entry.options == before
    try:
        result = await commission(hass, entry)
    except InvalidData:
        result = None  # Current native form cannot accept nutrient commissioning.
    assert entry.options.get("dosing_parameters") == DOSING
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["settings_revision"] == 1
    assert (
        entry.options["control"]["nutrient_binding"]["registry_id"]
        == hass.data["p3_fixture"]["rows"][0].id
    )
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    fields = {str(key): key.description or {} for key in flow["data_schema"].schema}
    assert fields["pulse_seconds"]["suggested_value"] == 2
    assert fields["nutrient_commissioned"]["suggested_value"] is True
    assert (
        fields["nutrient_output"]["suggested_value"] == hass.data["p3_fixture"]["rows"][0].entity_id
    )
    assert (
        fields["circulation_output"]["suggested_value"]
        == hass.data["p3_fixture"]["rows"][1].entity_id
    )
    hass.config_entries.options.async_abort(flow["flow_id"])
    assert not hass.data["p3_fixture"]["calls"]
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize("key", ["pulse_seconds", "safe_min_level_m", "stable_samples"])
async def test_native_numeric_selector_does_not_erase_boolean(nutrient_hass, key):
    from p3_fixtures import nutrient_payload

    hass = nutrient_hass
    entry = await add_tank(hass)
    before = dict(entry.options)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    values = nutrient_payload(hass)
    values[key] = True
    try:
        result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    except InvalidData:
        result = None
    assert entry.options == before, "Native selector must reject bool before float coercion"
    assert result is None or result["type"] == FlowResultType.FORM
    assert not hass.data["p3_fixture"]["calls"]
