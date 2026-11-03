"""Start service native acceptance."""
import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, configure, control_hass, target, toggle  # noqa: F401
from conftest import DOMAIN


async def test_service_start_returns_receipt_and_drives_same_native_switch(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    result = await hass.services.async_call(DOMAIN, "start_flow", {"config_entry_id": tank.entry_id},
        blocking=True, return_response=True)
    assert hass.data["p2_fixture"]["calls"], "Service must drive native output"
    assert result["accepted"] is True
    assert isinstance(result["run_id"], str)
    assert hass.states.get(target(hass, tank, "switch", "flow_run")).state == "on"
