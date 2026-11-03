"""Native isolated P2 acceptance. Never contacts an external HA."""

import pytest
from conftest import DOMAIN, entry
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er


async def add_tank(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    return tank


def option_payload(hass, **updates):
    return {
        "ph": "sensor.ph",
        "ec": "sensor.ec",
        "level": "sensor.level",
        "max_age_seconds": 300,
        "refill_output": hass.data["p2_fixture"]["row"].entity_id,
        "commissioned": True,
        "feedback_timeout": 10,
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
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {"entity_id": target(hass, tank, "switch", key)},
        blocking=True,
    )


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


@pytest.mark.parametrize(
    "reason", ["source_invalid", "level_not_low", "output_not_off", "weekday", "uncommissioned"]
)
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
        hass.config_entries.async_update_entry(
            tank,
            options={**tank.options, "control": {**tank.options["control"], "commissioned": False}},
        )
    with pytest.raises(ServiceValidationError, match=reason):
        await toggle(hass, tank, "flow_run")
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize("cause", ["source", "master", "refill", "external_off", "timeout"])
async def test_running_safety_stop(control_hass, cause):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    if cause == "source":
        hass.states.async_set("sensor.ec", "unavailable")
    elif cause in ("master", "refill"):
        await toggle(
            hass, tank, "automation_enabled" if cause == "master" else "refill_enabled", False
        )
    elif cause == "external_off":
        hass.data["p2_fixture"]["hardware"]._attr_is_on = False
        hass.data["p2_fixture"]["hardware"].async_write_ha_state()
    else:
        tank.runtime_data.control.started -= 190 * 60 + 1
        await tank.runtime_data.control.evaluate()
    await hass.async_block_till_done()
    assert hass.data["p2_fixture"]["calls"][-1][0] == "turn_off"
    assert hass.states.get(target(hass, tank, "switch", "flow_run")).state == "off"
