"""Native authorization gate tests."""

import pytest
from conftest import DOMAIN
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from test_p2_control import add_tank, configure, toggle  # noqa: F401


@pytest.mark.parametrize("kind", ["unknown", "nonadmin", "inactive"])
async def test_start_service_requires_active_admin(control_hass, kind):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    from homeassistant.auth import auth_manager_from_config

    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("owner")
    user = await hass.auth.async_create_user("test")
    if kind == "inactive":
        await hass.auth.async_update_user(user, is_active=False)
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "start_flow",
            {"config_entry_id": tank.entry_id},
            blocking=True,
            context=Context(user_id="absent" if kind == "unknown" else user.id),
        )
    assert not hass.data["p2_fixture"]["calls"]
    assert tank.runtime_data.control.running is False, "Denied principal must not mutate admission"


async def test_domain_authorizes_before_target_lookup(control_hass):
    from homeassistant.auth import auth_manager_from_config
    hass = control_hass
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, DOMAIN, {})
    hass.auth = await auth_manager_from_config(hass, [], [])
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, "start_flow", {"config_entry_id": "absent"}, blocking=True, context=Context(user_id="absent"))
