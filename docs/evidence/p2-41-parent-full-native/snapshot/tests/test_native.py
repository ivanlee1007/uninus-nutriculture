from conftest import entry
from homeassistant.helpers import entity_registry as er


async def test_native_owned_numbers_and_status(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    rows = er.async_entries_for_config_entry(er.async_get(hass), tank.entry_id)
    numbers = [r for r in rows if r.domain == "number"]
    assert len(numbers) == 10
    assert len([r for r in rows if r.domain == "sensor"]) == 2
    defaults = {
        "level_low": 2.25,
        "level_high": 2.4,
        "ph_low": 5.4,
        "ph_high": 5.8,
        "ec_low": 0.8,
        "ec_high": 0.9,
        "refill_timeout": 190,
        "ec_timeout": 90,
        "ph_timeout": 190,
        "mix_duration": 10,
    }
    for r in numbers:
        key = r.unique_id.split(":")[-1]
        state = hass.states.get(r.entity_id)
        assert float(state.state) == defaults[key]
        assert state.attributes["mode"] == "box"
        assert str(r.entity_category) == "config"
    status = hass.states.get(
        next(r.entity_id for r in rows if r.unique_id == f"{tank.entry_id}:status")
    )
    assert status.state == "within_range"
    assert status.attributes["schema_version"] == 1
    assert status.attributes["mode"] == "shadow"
    assert status.attributes["ready_for_irrigation"] is False
    assert status.attributes["parameters"] == defaults
    assert len(status.attributes["parameter_entities"]) == 10

    control = hass.states.get(
        next(r.entity_id for r in rows if r.unique_id == f"{tank.entry_id}:control_status")
    )
    assert control.attributes["schema_version"] == 2
    assert control.attributes["mode"] == "control"
    assert control.attributes["ready_for_irrigation"] is False
    assert control.state == "uncommissioned"
