"""Native service metadata and rejected queued settings are observable."""

import asyncio

import pytest
from conftest import DOMAIN
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service
from p3_fixtures import commission
from p3_fixtures import nutrient_hass as nutrient_hass
from test_p2_control import add_tank
from test_p3_settings import payload


async def test_group_service_fields_are_visible_in_native_discovery(nutrient_hass):
    hass = nutrient_hass
    await add_tank(hass)
    descriptions = await service.async_get_all_descriptions(hass)
    fields = descriptions.get(DOMAIN, {}).get("apply_control_settings", {}).get("fields", {})
    assert set(fields) == {
        "config_entry_id",
        "expected_revision",
        "parameters",
        "dosing_parameters",
        "allowed_weekdays",
    }, "A registered action without its native field descriptors is not operable in the UI"
    assert fields["config_entry_id"]["selector"] == {"config_entry": {"integration": DOMAIN}}
    assert not hass.data["p3_fixture"]["calls"]


async def test_removed_admin_queued_at_settings_lock_cannot_commit(nutrient_hass):
    hass = nutrient_hass
    entry = await add_tank(hass)
    await commission(hass, entry)
    # Keep the actual owner separate from the revocable administrator.
    from homeassistant.auth import auth_manager_from_config

    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("Owner")
    admin = await hass.auth.async_create_user("Queued admin", group_ids=[GROUP_ID_ADMIN])
    assert admin.is_admin and not admin.is_owner
    tank = entry.runtime_data
    data = payload(entry)
    data["parameters"].update(ec_low=0.9, ec_high=1.1)
    before_options = dict(entry.options)
    before_parameters = dict(tank.parameters)
    await tank.lock.acquire()
    task = asyncio.create_task(
        hass.services.async_call(
            DOMAIN,
            "apply_control_settings",
            data,
            blocking=True,
            context=Context(user_id=admin.id),
            return_response=True,
        )
    )
    try:
        async with asyncio.timeout(2):
            while not tank.lock._waiters:
                await asyncio.sleep(0)
        await hass.auth.async_remove_user(admin)
    finally:
        tank.lock.release()
    try:
        with pytest.raises(HomeAssistantError):
            await task
        assert entry.options == before_options
        assert tank.parameters == before_parameters
        assert not hass.data["p3_fixture"]["calls"]
        assert not hass.data["p2_fixture"]["calls"]
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
