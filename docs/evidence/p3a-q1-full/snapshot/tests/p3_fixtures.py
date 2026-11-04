"""Isolated native nutrient hardware and explicit operator declarations."""

import pytest_asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import entity_registry as er
from test_p2_control import option_payload

DOSING = {
    "safe_min_level_m": 0.5,
    "pulse_seconds": 2,
    "max_total_on_seconds": 20,
    "max_pulses": 5,
    "post_mix_seconds": 300,
    "sample_wait_timeout_seconds": 600,
    "stable_samples": 8,
    "stable_interval_seconds": 300,
    "flow_timeout_seconds": 5400,
    "ph_danger_low": 3.8,
    "ec_danger_high": 1.3,
    "ph_high_alarm": 6.8,
    "ph_high_alarm_seconds": 600,
}


@pytest_asyncio.fixture
async def nutrient_hass(control_hass):
    hass = control_hass
    calls = []

    class Output(SwitchEntity):
        _attr_should_poll = False
        _attr_is_on = False

        def __init__(self, key):
            self._attr_name = "Fixture " + key
            self._attr_unique_id = "p3-" + key

        async def async_turn_on(self, **kwargs):
            calls.append((self.entity_id, "on"))
            self._attr_is_on = True
            self.async_write_ha_state()

        async def async_turn_off(self, **kwargs):
            calls.append((self.entity_id, "off"))
            self._attr_is_on = False
            self.async_write_ha_state()

    outputs = [Output(key) for key in ("nutrient", "circulation")]
    await hass.data["switch"].async_add_entities(outputs)
    hass.data["p3_fixture"] = {
        "outputs": outputs,
        "calls": calls,
        "rows": [er.async_get(hass).async_get(output.entity_id) for output in outputs],
    }
    yield hass
    assert not calls, "A1 settings must never actuate outputs"


def nutrient_payload(hass, **updates):
    rows = hass.data["p3_fixture"]["rows"]
    return option_payload(
        hass,
        nutrient_output=rows[0].entity_id,
        circulation_output=rows[1].entity_id,
        nutrient_commissioned=True,
        nutrient_protection_confirmed=True,
        device_max_on_seconds=5,
        alias_notes="Independent outputs, fixture protection only",
        sample_mode="reported",
        report_contract_confirmed=True,
        **DOSING,
        **updates,
    )


async def commission(hass, entry, **updates):
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], nutrient_payload(hass, **updates)
    )
    await hass.async_block_till_done()
    return result
