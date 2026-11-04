"""Actual native Sensor schema3 with the connected nutrient engine."""

from p3_fixtures import DOSING, commission
from p3_fixtures import nutrient_hass as nutrient_hass
from test_p2_control import add_tank, target


async def test_native_schema3_projects_commissioning_without_fake_capability(nutrient_hass):
    hass = nutrient_hass
    entry = await add_tank(hass)
    sensor = target(hass, entry, "sensor", "control_status")
    assert hass.states.get(sensor).attributes["schema_version"] == 2
    await commission(hass, entry)
    state = hass.states.get(sensor)
    attrs = state.attributes
    assert attrs["schema_version"] == 3
    assert attrs["settings_target"] == {
        "config_entry_id": entry.entry_id,
        "service": "apply_control_settings",
    }
    assert attrs["settings_revision"] == 1
    assert attrs["dosing_parameters"] == DOSING
    assert attrs["capabilities"] == {"refill": True, "nutrient": True, "acid": False, "mix": False}
    assert attrs["flow_state"] == state.state
    assert attrs["nutrient_phase"] is None
    assert attrs["dose_progress"] == {"pulse_count": 0, "reserved_on_seconds": 0, "stable_count": 0}
    assert attrs["output_states"] == {"nutrient": "off", "circulation": "off"}
    assert attrs["control_entities"]["nutrient_enabled"] == target(
        hass, entry, "switch", "nutrient_enabled"
    )
    assert hass.states.get(target(hass, entry, "switch", "nutrient_enabled")).state == "off"
    assert attrs["stage_states"]["nutrient"] == "idle"
    assert (
        len(hass.states.get(target(hass, entry, "sensor", "status")).attributes["parameters"]) == 10
    )
