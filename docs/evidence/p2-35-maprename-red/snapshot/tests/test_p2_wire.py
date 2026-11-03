"""Control wire acceptance over actual HA entities."""

from test_p2_control import add_tank, configure, target  # noqa: F401


async def test_control_sensor_wire_is_separate_from_shadow(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    state = hass.states.get(target(hass, tank, "sensor", "control_status"))
    assert state is not None, "Missing native control status"
    assert state.state == "disabled", "Commissioned but not enabled must be disabled"
    data = state.attributes
    assert data["schema_version"] == 2
    assert data["mode"] == "control"
    assert data["ready_for_irrigation"] is False
    assert len(data["parameters"]) == 10
    assert data["capabilities"] == {"refill": True, "nutrient": False, "acid": False, "mix": False}
    assert data["control_entities"]["flow_run"] == target(hass, tank, "switch", "flow_run")
    assert "nutrient_enabled" not in data["control_entities"]
    assert hass.states.get(target(hass, tank, "sensor", "status")).attributes["schema_version"] == 1


async def test_control_target_map_follows_native_switch_rename_immediately(control_hass):
    from homeassistant.helpers import entity_registry as er
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    er.async_get(hass).async_update_entity(target(hass, tank, "switch", "flow_run"), new_entity_id="switch.renamed_flow")
    await hass.async_block_till_done()
    status = hass.states.get(target(hass, tank, "sensor", "control_status"))
    assert status.attributes["control_entities"].get("flow_run") == "switch.renamed_flow"
