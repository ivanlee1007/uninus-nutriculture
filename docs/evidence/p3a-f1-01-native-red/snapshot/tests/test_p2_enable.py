"""Enable gates and unavailable P3 entities."""

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_buttons import press
from test_p2_control import add_tank, configure, target, toggle  # noqa: F401


@pytest.mark.parametrize("condition", ["uncommissioned", "fault", "unsupported"])
async def test_enable_gate(control_hass, condition):
    hass = control_hass
    tank = await add_tank(hass)
    if condition != "uncommissioned":
        await configure(hass, tank)
    if condition == "fault":
        await press(hass, tank, "emergency_stop")
    if condition == "unsupported":
        assert (
            hass.states.get(target(hass, tank, "switch", "nutrient_enabled")).state == "unavailable"
        )
    else:
        with pytest.raises(ServiceValidationError):
            await toggle(hass, tank, "automation_enabled")
    assert not hass.data["p2_fixture"]["calls"]
