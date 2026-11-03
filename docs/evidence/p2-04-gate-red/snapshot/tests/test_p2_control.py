"""Native isolated P2 acceptance. Never contacts an external HA."""

import pytest
import pytest_asyncio
from conftest import DOMAIN, entry, make_hass
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


@pytest_asyncio.fixture
async def control_hass(tmp_path):
    hass = await make_hass(tmp_path / "control-ha")
    for key, value, unit in (("ph", 5.6, "pH"), ("ec", 0.85, "mS/cm"), ("level", 2, "m")):
        hass.states.async_set("sensor." + key, value, {"unit_of_measurement": unit})
    calls = []

    from homeassistant.components.switch import SwitchEntity
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "switch", {})

    class Hardware(SwitchEntity):
        _attr_name = "Fixture refill"
        _attr_unique_id = "refill-output"
        _attr_is_on = False
        _attr_should_poll = False

        async def async_turn_on(self, **kwargs):
            calls.append(("turn_on", {"entity_id": self.entity_id}, self._context))
            self._attr_is_on = True
            self.async_write_ha_state()

        async def async_turn_off(self, **kwargs):
            calls.append(("turn_off", {"entity_id": self.entity_id}, self._context))
            self._attr_is_on = False
            self.async_write_ha_state()

    hardware = Hardware()
    await hass.data["switch"].async_add_entities([hardware])
    row = er.async_get(hass).async_get(hardware.entity_id)
    hass.data["p2_fixture"] = {"row": row, "calls": calls, "hardware": hardware}
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


def target(hass, tank, domain, key):
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{tank.entry_id}:{key}")


async def toggle(hass, tank, key, on=True):
    await hass.services.async_call("switch", "turn_on" if on else "turn_off",
        {"entity_id": target(hass, tank, "switch", key)}, blocking=True)


async def test_native_refill_switch_high_level_stops(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    assert hass.data["p2_fixture"]["calls"][0][0] == "turn_on"
    assert hass.states.get(target(hass, tank, "switch", "flow_run")).state == "on"
    hass.states.async_set("sensor.level", 2.4, {"unit_of_measurement": "m"})
    await hass.async_block_till_done()
    assert hass.data["p2_fixture"]["calls"][-1][0] == "turn_off"
    assert hass.states.get(target(hass, tank, "switch", "flow_run")).state == "off"


async def test_disabled_start_has_no_output(control_hass):
    import pytest
    from homeassistant.exceptions import ServiceValidationError
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    with pytest.raises(ServiceValidationError, match="disabled"):
        await toggle(hass, tank, "flow_run")
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize("reason", ["source_invalid", "level_not_low", "output_not_off", "weekday", "uncommissioned"])
async def test_start_gate_rejects_without_output(control_hass, reason):
    from homeassistant.exceptions import ServiceValidationError
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    if reason == "source_invalid":
        hass.states.async_set("sensor.ph", "unavailable")
    elif reason == "level_not_low":
        hass.states.async_set("sensor.level", 2.3, {"unit_of_measurement": "m"})
    elif reason == "output_not_off":
        hass.states.async_set(hass.data["p2_fixture"]["row"].entity_id, "unavailable")
    elif reason == "weekday":
        await configure(hass, tank, refill_weekdays=[])
    else:
        hass.config_entries.async_update_entry(tank, options={**tank.options,
            "control": {**tank.options["control"], "commissioned": False}})
    with pytest.raises(ServiceValidationError, match=reason):
        await toggle(hass, tank, "flow_run")
    assert not hass.data["p2_fixture"]["calls"]


