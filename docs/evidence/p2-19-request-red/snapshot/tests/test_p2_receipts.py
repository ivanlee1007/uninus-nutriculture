"""Finite request receipts do not queue new runs."""
import pytest
from homeassistant.exceptions import ServiceValidationError
from conftest import DOMAIN
from test_p2_control import add_tank, configure, control_hass, toggle  # noqa: F401


async def test_busy_service_and_idempotent_receipt(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    data = {"config_entry_id": tank.entry_id, "request_id": "one"}
    receipt = await hass.services.async_call(DOMAIN, "start_flow", data, blocking=True, return_response=True)
    await toggle(hass, tank, "flow_run")
    assert len(hass.data["p2_fixture"]["calls"]) == 1
    with pytest.raises(ServiceValidationError, match="busy"):
        await hass.services.async_call(DOMAIN, "start_flow", {"config_entry_id": tank.entry_id}, blocking=True)
    await toggle(hass, tank, "flow_run", False)
    repeated = await hass.services.async_call(DOMAIN, "start_flow", data, blocking=True, return_response=True)
    assert repeated == receipt
    assert len(hass.data["p2_fixture"]["calls"]) == 2
