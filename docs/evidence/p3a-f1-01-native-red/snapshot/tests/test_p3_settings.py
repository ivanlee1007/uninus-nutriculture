"""Native registered group service / CAS and Number integration."""

import pytest
from conftest import DOMAIN
from homeassistant.exceptions import ServiceNotFound, ServiceValidationError
from p3_fixtures import commission
from p3_fixtures import nutrient_hass as nutrient_hass
from test_p2_control import add_tank, target


def payload(entry, **updates):
    return {
        "config_entry_id": entry.entry_id,
        "expected_revision": entry.options.get("settings_revision", 0),
        "parameters": dict(entry.runtime_data.parameters),
        "dosing_parameters": dict(entry.options["dosing_parameters"]),
        "allowed_weekdays": dict(entry.options["control"]["allowed_weekdays"]),
        **updates,
    }


async def apply(hass, data):
    return await hass.services.async_call(
        DOMAIN, "apply_control_settings", data, blocking=True, return_response=True
    )


async def test_registered_atomic_apply_cas_and_number_revision(nutrient_hass):
    hass = nutrient_hass
    entry = await add_tank(hass)
    await commission(hass, entry)
    data = payload(entry)
    data["parameters"].update(ec_low=0.9, ec_high=1.1)
    try:
        result = await apply(hass, data)
    except ServiceNotFound:
        result = None
    assert entry.options.get("parameters", {}).get("ec_low") == 0.9
    assert result == {"applied": True, "settings_revision": 2}
    runtime = entry.runtime_data
    assert await apply(hass, payload(entry)) == result  # Identical save is a no-op.
    before = dict(entry.options)
    with pytest.raises(ServiceValidationError, match="settings_conflict"):
        await apply(hass, data)
    assert entry.options == before
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": target(hass, entry, "number", "ph_low"),
            "value": 5.5,
        },
        blocking=True,
    )
    assert entry.options["settings_revision"] == 3
    assert entry.runtime_data is runtime  # Group / Number must not reload control.
    invalid = payload(entry)
    invalid["parameters"]["ec_high"] = 1.4  # Above danger threshold.
    before = dict(entry.options)
    with pytest.raises(ServiceValidationError):
        await apply(hass, invalid)
    assert entry.options == before
    assert not hass.data["p2_fixture"]["calls"]
