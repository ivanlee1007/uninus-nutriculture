import asyncio

import pytest
from conftest import entry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from test_writes import change, ids


@pytest.mark.parametrize("operation", ["rename", "disable", "delete"])
async def test_queued_old_number_identity_cannot_write_after_registry_change(hass, operation):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    entities = ids(hass, tank)
    number = hass.data["number"].get_entity(entities["ph_low"])
    manager = tank.runtime_data
    await manager.lock.acquire()
    pending = asyncio.create_task(number.async_set_native_value(5.5))
    await asyncio.sleep(0)
    registry = er.async_get(hass)
    if operation == "rename":
        registry.async_update_entity(entities["ph_low"], new_entity_id="number.renamed_limit")
    elif operation == "disable":
        registry.async_update_entity(entities["ph_low"], disabled_by=er.RegistryEntryDisabler.USER)
    else:
        registry.async_remove(entities["ph_low"])
    # Do not use block_till_done: the intentionally blocked writer is unfinished.
    for _ in range(20):
        await asyncio.sleep(0)
    manager.lock.release()
    with pytest.raises(HomeAssistantError):
        await pending
    assert not tank.options
    await hass.async_block_till_done()
    if operation == "rename":
        await change(hass, "number.renamed_limit", 5.5)
        assert tank.options["parameters"]["ph_low"] == 5.5


async def test_native_metadata_all_ten_exact_and_missing_target_omitted(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    entities = ids(hass, tank)
    for key, entity_id in entities.items():
        if key == "status":
            continue
        state = hass.states.get(entity_id)
        group = key.split("_")[0]
        minimum, maximum, step, unit = (
            {
                "level": (0, 10, 0.01, "m"),
                "ph": (0, 14, 0.1, None),
                "ec": (0, 20, 0.01, "mS/cm"),
            }.get(group, (1, 1440, 1, "min"))
            if not key.endswith("timeout")
            else (1, 1440, 1, "min")
        )
        assert state.attributes["min"] == minimum
        assert state.attributes["max"] == maximum
        assert state.attributes["step"] == step
        assert state.attributes.get("unit_of_measurement") == unit
    hass.states.async_remove(entities["ec_low"])
    await hass.async_block_till_done()
    assert "ec_low" not in hass.states.get(entities["status"]).attributes["parameter_entities"]


@pytest.mark.parametrize(
    "unusable", ["unavailable", "unknown", "NaN", "Infinity", "-Infinity", "not-a-number", None]
)
async def test_unusable_number_omitted_from_status_until_native_recovery(hass, unusable):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    entities = ids(hass, tank)
    entity_id = entities["ph_low"]
    number = hass.data["number"].get_entity(entity_id)
    original = hass.states.get(entity_id)
    expected = dict(hass.states.get(entities["status"]).attributes["parameter_entities"])
    assert expected["ph_low"] == entity_id
    parameters = dict(tank.runtime_data.parameters)
    options = dict(tank.options)

    if unusable is None:
        hass.states.async_remove(entity_id)
    else:
        hass.states.async_set(entity_id, unusable, dict(original.attributes))
    await hass.async_block_till_done()
    assert hass.states.get(entities["status"]).attributes["parameter_entities"] == {
        key: target for key, target in expected.items() if key != "ph_low"
    }

    # Restore through the actual native Number, not a guessed replacement ID.
    number.async_write_ha_state()
    await hass.async_block_till_done()
    assert hass.states.get(entities["status"]).attributes["parameter_entities"] == expected
    assert hass.states.get(entity_id).state == original.state
    assert tank.runtime_data.parameters == parameters
    assert dict(tank.options) == options
