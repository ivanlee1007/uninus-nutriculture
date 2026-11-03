"""Native isolated P2 acceptance. Never contacts an external HA."""

import pytest_asyncio
from conftest import DOMAIN, entry, make_hass
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


@pytest_asyncio.fixture
async def control_hass(tmp_path):
    hass = await make_hass(tmp_path / "control-ha")
    for key, value, unit in (("ph", 5.6, "pH"), ("ec", 0.85, "mS/cm"), ("level", 2, "m")):
        hass.states.async_set("sensor." + key, value, {"unit_of_measurement": unit})
    calls = []

    @callback
    def output(call):
        calls.append((call.service, dict(call.data), call.context))
        hass.states.async_set(call.data["entity_id"], "on" if call.service == "turn_on" else "off")

    for service in ("turn_on", "turn_off"):
        hass.services.async_register("switch", service, output)
    row = er.async_get(hass).async_get_or_create("switch", "p2_fixture", "refill-output")
    hass.states.async_set(row.entity_id, "off")
    hass.data["p2_fixture"] = {"row": row, "calls": calls}
    yield hass
    await hass.async_stop(force=True)


async def add_tank(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    return tank


def option_payload(hass, **updates):
    return {
        "ph": "sensor.ph", "ec": "sensor.ec", "level": "sensor.level",
        "max_age_seconds": 300,
        "refill_output": hass.data["p2_fixture"]["row"].entity_id,
        "commissioned": True, "feedback_timeout": 10,
        **updates,
    }


async def configure(hass, tank, **updates):
    flow = await hass.config_entries.options.async_init(tank.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], option_payload(hass, **updates)
    )
    await hass.async_block_till_done()
    return result


async def test_native_options_commission_saves_registry_identity_without_output(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    result = await configure(hass, tank)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert tank.options.get("control", {}).get("commissioned") is True
    binding = tank.options["control"]["binding"]
    assert binding["registry_id"] == hass.data["p2_fixture"]["row"].id
    assert tank.options["control"]["feedback_timeout"] == 10
    assert not hass.data["p2_fixture"]["calls"]
