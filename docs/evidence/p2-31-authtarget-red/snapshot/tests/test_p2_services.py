"""Start service native acceptance."""

import pytest
from conftest import DOMAIN
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, configure, target, toggle  # noqa: F401


async def test_service_start_returns_receipt_and_drives_same_native_switch(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    result = await hass.services.async_call(
        DOMAIN,
        "start_flow",
        {"config_entry_id": tank.entry_id},
        blocking=True,
        return_response=True,
    )
    assert hass.data["p2_fixture"]["calls"], "Service must drive native output"
    assert result["accepted"] is True
    assert isinstance(result["run_id"], str)
    assert hass.states.get(target(hass, tank, "switch", "flow_run")).state == "on"


@pytest.mark.parametrize("request_id", ["", "x" * 129, None])
async def test_invalid_request_identity_is_rejected(control_hass, request_id):
    import voluptuous as vol

    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await hass.services.async_call(
            DOMAIN,
            "start_flow",
            {"config_entry_id": tank.entry_id, "request_id": request_id},
            blocking=True,
        )
    assert not hass.data["p2_fixture"]["calls"]


async def test_unloaded_entry_rejects_even_if_stale_runtime_is_reintroduced(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    runtime = tank.runtime_data
    assert await hass.config_entries.async_unload(tank.entry_id)
    runtime.active = True
    runtime.control.master = True
    tank.runtime_data = runtime
    with pytest.raises(ServiceValidationError, match="entry_not_loaded"):
        await hass.services.async_call(DOMAIN, "start_flow", {"config_entry_id": tank.entry_id}, blocking=True)
    assert not hass.data["p2_fixture"]["calls"]
