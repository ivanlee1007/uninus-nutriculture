"""Native service and persistence acceptance."""

from conftest import entry
from homeassistant.helpers import entity_registry as er


def ids(hass, tank):
    return {
        r.unique_id.split(":")[-1]: r.entity_id
        for r in er.async_entries_for_config_entry(er.async_get(hass), tank.entry_id)
        if r.domain == "number" or r.unique_id == f"{tank.entry_id}:status"
    }


async def change(hass, entity_id, value):
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True
    )
    await hass.async_block_till_done()


async def test_native_write_updates_status_siblings_and_options(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    entities = ids(hass, tank)
    await change(hass, entities["ph_low"], 5.5)
    assert float(hass.states.get(entities["ph_low"]).state) == 5.5
    assert tank.options["parameters"]["ph_low"] == 5.5
    assert hass.states.get(entities["status"]).attributes["parameters"]["ph_low"] == 5.5
    assert float(hass.states.get(entities["ph_high"]).state) == 5.8
