"""Supplementary native boundary coverage (not historical RED claims)."""

import asyncio
from datetime import timedelta

import pytest
import voluptuous as vol
from conftest import DOMAIN
from homeassistant.auth import auth_manager_from_config
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from test_p2_buttons import press
from test_p2_control import add_tank, configure, target, toggle


async def ready(hass):
    tank = await add_tank(hass)
    await configure(hass, tank)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    return tank


@pytest.mark.parametrize("payload", [{}, {"config_entry_id": None}, {"config_entry_id": "absent"}])
async def test_service_requires_explicit_loaded_target_without_entries(control_hass, payload):
    hass = control_hass
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(DOMAIN, "start_flow", payload, blocking=True)
    assert not hass.data["p2_fixture"]["calls"]


async def test_wrong_domain_entry_is_rejected(control_hass):
    hass = control_hass
    assert await async_setup_component(hass, DOMAIN, {})
    from homeassistant.config_entries import ConfigEntry

    foreign = ConfigEntry(
        domain="switch",
        title="Foreign",
        data={},
        options={},
        source="user",
        version=1,
        minor_version=1,
        unique_id=None,
        discovery_keys={},
        subentries_data=[],
    )
    # A real registered ConfigEntry; deliberately not loaded as our domain.
    hass.config_entries._entries[foreign.entry_id] = foreign
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "start_flow", {"config_entry_id": foreign.entry_id}, blocking=True
        )
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize("kind", ["past", "future", "missing", "unit", "nan"])
async def test_necessary_source_validity_not_quality_gates_start(control_hass, kind):
    hass = control_hass
    tank = await ready(hass)
    source = hass.states.get("sensor.ec")
    if kind == "missing":
        hass.states.async_remove(source.entity_id)
    elif kind == "unit":
        hass.states.async_set(source.entity_id, 0.85, {"unit_of_measurement": "uS/cm"})
    elif kind == "nan":
        hass.states.async_set(source.entity_id, "NaN", source.attributes)
    else:
        seconds = -301 if kind == "past" else 60
        hass.states.async_set(
            source.entity_id,
            source.state,
            source.attributes,
            timestamp=(dt_util.utcnow() + timedelta(seconds=seconds)).timestamp(),
        )
    with pytest.raises(ServiceValidationError, match="source_invalid"):
        await toggle(hass, tank, "flow_run")
    assert not hass.data["p2_fixture"]["calls"]


async def test_quality_out_of_range_still_allows_refill_and_optional_response_is_none(control_hass):
    hass = control_hass
    tank = await ready(hass)
    hass.states.async_set("sensor.ec", 2, {"unit_of_measurement": "mS/cm"})
    response = await hass.services.async_call(
        DOMAIN, "start_flow", {"config_entry_id": tank.entry_id}, blocking=True
    )
    assert response is None
    assert hass.data["p2_fixture"]["calls"][0][0] == "turn_on"


async def test_equal_value_report_expiry_is_seen_by_backend_timer(control_hass):
    hass = control_hass
    tank = await ready(hass)
    await toggle(hass, tank, "flow_run")
    source = hass.states.get("sensor.ph")
    hass.states.async_set(
        source.entity_id,
        source.state,
        source.attributes,
        timestamp=(dt_util.utcnow() - timedelta(seconds=301)).timestamp(),
    )
    await asyncio.sleep(1.1)
    await hass.async_block_till_done()
    assert hass.data["p2_fixture"]["calls"][-1][0] == "turn_off"
    assert tank.runtime_data.control.fault == "source_invalid"


@pytest.mark.parametrize("operation", ["rename", "disable", "remove", "replace"])
async def test_registry_binding_tracks_only_stable_identity(control_hass, operation):
    hass = control_hass
    tank = await ready(hass)
    row = hass.data["p2_fixture"]["row"]
    registry = er.async_get(hass)
    if operation == "rename":
        registry.async_update_entity(row.entity_id, new_entity_id="switch.renamed_physical_output")
        await hass.async_block_till_done()
        await toggle(hass, tank, "flow_run")
        assert (
            hass.data["p2_fixture"]["calls"][0][1]["entity_id"] == "switch.renamed_physical_output"
        )
    else:
        if operation == "disable":
            registry.async_update_entity(row.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
        else:
            registry.async_remove(row.entity_id)
            if operation == "replace":
                registry.async_get_or_create(
                    "switch", "replacement_fixture", "other", suggested_object_id="fixture_refill"
                )
                hass.states.async_set(row.entity_id, "off")
        await hass.async_block_till_done()
        with pytest.raises(ServiceValidationError):
            await toggle(hass, tank, "flow_run")
        assert not hass.data["p2_fixture"]["calls"]


async def test_busy_commissioning_change_is_rejected_without_dispatch(control_hass):
    hass = control_hass
    tank = await ready(hass)
    old = dict(tank.options)
    result = await configure(hass, tank, commissioned=False)
    assert result["errors"]["base"] == "control_busy"
    assert tank.options == old
    assert not hass.data["p2_fixture"]["calls"]


async def test_reset_requires_necessary_sources_and_known_off(control_hass):
    hass = control_hass
    tank = await ready(hass)
    await press(hass, tank, "emergency_stop")
    hass.states.async_set("sensor.ph", "unavailable")
    with pytest.raises(ServiceValidationError, match="reset_unsafe"):
        await press(hass, tank, "reset_fault")
    assert tank.runtime_data.control.fault == "emergency_stop"
    assert not tank.runtime_data.control.master
    assert not hass.data["p2_fixture"]["calls"]


async def test_revoked_admin_after_lock_wait_cannot_start(control_hass):
    hass = control_hass
    tank = await ready(hass)
    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("owner")
    admin = await hass.auth.async_create_user("admin", group_ids=["system-admin"])
    control = tank.runtime_data.control
    await control.lock.acquire()
    request = asyncio.create_task(
        hass.services.async_call(
            DOMAIN,
            "start_flow",
            {"config_entry_id": tank.entry_id},
            blocking=True,
            context=Context(user_id=admin.id),
        )
    )
    await asyncio.sleep(0.02)
    assert not request.done()
    await hass.auth.async_update_user(admin, group_ids=["system-users"])
    control.lock.release()
    with pytest.raises(Unauthorized):
        await request
    assert not hass.data["p2_fixture"]["calls"]


@pytest.mark.parametrize(
    "domain,key", [("switch", "automation_enabled"), ("button", "emergency_stop")]
)
async def test_native_human_controls_share_admin_policy(control_hass, domain, key):
    hass = control_hass
    tank = await ready(hass)
    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("owner")
    user = await hass.auth.async_create_user("ordinary", group_ids=["system-users"])
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            domain,
            "turn_on" if domain == "switch" else "press",
            {"entity_id": target(hass, tank, domain, key)},
            blocking=True,
            context=Context(user_id=user.id),
        )
    assert tank.runtime_data.control.fault is None
    assert not hass.data["p2_fixture"]["calls"]


async def test_admin_context_reaches_native_output(control_hass):
    hass = control_hass
    tank = await ready(hass)
    hass.auth = await auth_manager_from_config(hass, [], [])
    owner = await hass.auth.async_create_user("owner")
    context = Context(user_id=owner.id)
    await hass.services.async_call(
        DOMAIN, "start_flow", {"config_entry_id": tank.entry_id}, blocking=True, context=context
    )
    assert hass.data["p2_fixture"]["calls"][0][2].user_id == owner.id
