"""Preserve human stop provenance without making safe OFF depend on that user."""

import asyncio

import pytest
from homeassistant.auth import auth_manager_from_config
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from test_p2_acceptance import ready
from test_p2_control import target


@pytest.mark.parametrize(
    "key", ["flow_run", "automation_enabled", "refill_enabled", "emergency_stop"]
)
async def test_human_stop_reaches_output_with_causal_context(control_hass, key):
    hass = control_hass
    tank = await ready(hass)
    hass.auth = await auth_manager_from_config(hass, [], [])
    owner = await hass.auth.async_create_user("owner")
    start_context = Context(user_id=owner.id)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": target(hass, tank, "switch", "flow_run")},
        blocking=True,
        context=start_context,
    )
    stop_context = Context(user_id=owner.id)
    domain = "button" if key == "emergency_stop" else "switch"
    await hass.services.async_call(
        domain,
        "press" if domain == "button" else "turn_off",
        {"entity_id": target(hass, tank, domain, key)},
        blocking=True,
        context=stop_context,
    )
    calls = hass.data["p2_fixture"]["calls"]
    assert calls[-1][0] == "turn_off"
    assert calls[-1][2].id == stop_context.id or calls[-1][2].parent_id == stop_context.id
    assert hass.states.get(hass.data["p2_fixture"]["hardware"].entity_id).state == "off"


async def test_user_removed_during_on_does_not_block_traced_safety_off(control_hass):
    hass = control_hass
    tank = await ready(hass)
    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("owner")
    admin = await hass.auth.async_create_user("admin", group_ids=["system-admin"])
    origin = Context(user_id=admin.id)
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware.on_entered, hardware.on_release = asyncio.Event(), asyncio.Event()
    request = asyncio.create_task(
        hass.services.async_call(
            "uninus_nutriculture",
            "start_flow",
            {"config_entry_id": tank.entry_id},
            blocking=True,
            context=origin,
        )
    )
    await asyncio.wait_for(hardware.on_entered.wait(), 2)
    await hass.auth.async_remove_user(admin)
    hardware.on_release.set()
    result = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 3)
    assert isinstance(result[0], HomeAssistantError)
    assert hass.states.get(hardware.entity_id).state == "off"
    off = hass.data["p2_fixture"]["calls"][-1]
    assert off[0] == "turn_off"
    assert off[2].parent_id == origin.id
    assert off[2].user_id is None
    assert not tank.runtime_data.control.running
