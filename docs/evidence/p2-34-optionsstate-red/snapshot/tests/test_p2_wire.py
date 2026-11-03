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
