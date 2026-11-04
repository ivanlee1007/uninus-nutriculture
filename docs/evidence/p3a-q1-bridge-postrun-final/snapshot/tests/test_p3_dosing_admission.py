"""Native per-opening authority and Registry identity admission."""

import asyncio

import pytest
from homeassistant.auth import auth_manager_from_config
from homeassistant.core import Context
from homeassistant.helpers import entity_registry as er
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import prepared


@pytest.mark.parametrize("revocation", ["delete", "demote", "inactive", "generation", "entry"])
async def test_circulation_ack_does_not_authorize_later_pump(dosing_hass, revocation):
    hass = dosing_hass
    entry = await prepared(hass)
    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("owner")
    admin = await hass.auth.async_create_user("admin", group_ids=["system-admin"])
    pump, circ = hass.data["p3_fixture"]["outputs"]
    circ.on_ack_gate = asyncio.Event()
    await hass.services.async_call(
        "uninus_nutriculture",
        "start_flow",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
        context=Context(user_id=admin.id),
    )
    try:
        await asyncio.wait_for(circ.entered_on.wait(), 2)
        if revocation == "delete":
            await hass.auth.async_remove_user(admin)
        elif revocation == "demote":
            await hass.auth.async_update_user(admin, group_ids=["system-users"])
        elif revocation == "inactive":
            await hass.auth.async_update_user(admin, is_active=False)
        elif revocation == "generation":
            entry.runtime_data.control.generation += 1
        else:
            entry.runtime_data.active = False
        circ.on_ack_gate.set()
        await asyncio.wait_for(circ.entered_off.wait(), 1)
        assert not pump.entered_on.is_set(), "A completed circulation ACK is not fresh ON authority"
        assert entry.runtime_data.control.fault is not None
    finally:
        circ.on_ack_gate.set()
        await entry.runtime_data.control.stop()


@pytest.mark.parametrize("revocation", ["delete", "demote"])
async def test_circulation_ack_rechecks_authority_without_any_pump(dosing_hass, revocation):
    hass = dosing_hass
    entry = await prepared(hass)
    hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("owner")
    admin = await hass.auth.async_create_user("admin", group_ids=["system-admin"])
    pump, circ = hass.data["p3_fixture"]["outputs"]
    circ.on_ack_gate = asyncio.Event()
    await hass.services.async_call(
        "uninus_nutriculture",
        "start_flow",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
        context=Context(user_id=admin.id),
    )
    try:
        await asyncio.wait_for(circ.entered_on.wait(), 2)
        if revocation == "delete":
            await hass.auth.async_remove_user(admin)
        else:
            await hass.auth.async_update_user(admin, group_ids=["system-users"])
        circ.on_ack_gate.set()
        await asyncio.wait_for(circ.entered_off.wait(), 0.75)
        assert not pump.entered_on.is_set()
        assert entry.runtime_data.control.fault, "Denied authority must latch a nonempty fault"
        assert not entry.runtime_data.control.master
    finally:
        circ.on_ack_gate.set()
        await entry.runtime_data.control.stop()


@pytest.mark.parametrize("already_open", [False, True])
async def test_weekday_only_at_final_stage_first_opening(dosing_hass, already_open):
    hass = dosing_hass
    entry = await prepared(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    controller = entry.runtime_data.control
    entered, release = asyncio.Event(), asyncio.Event()
    dispatch = controller.nutrient_dispatch

    async def held(role, enabled):
        if enabled and role == "circulation":
            entered.set()
            await release.wait()
        return await dispatch(role, enabled)

    controller.nutrient_dispatch = held
    circ.on_ack_gate = asyncio.Event()
    await hass.services.async_call(
        "uninus_nutriculture",
        "start_flow",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    try:
        await asyncio.wait_for(entered.wait(), 2)
        if already_open:
            release.set()
            await asyncio.wait_for(circ.entered_on.wait(), 2)
        options = entry.options
        config = options["control"]
        hass.config_entries.async_update_entry(
            entry,
            options={
                **options,
                "control": {
                    **config,
                    "allowed_weekdays": {**config["allowed_weekdays"], "nutrient": []},
                },
            },
        )
        release.set()
        circ.on_ack_gate.set()
        if already_open:
            await asyncio.wait_for(pump.entered_on.wait(), 1)
        else:
            await asyncio.wait_for(circ.entered_off.wait(), 1)
            assert not circ.entered_on.is_set()
            assert controller.fault == "weekday"
    finally:
        release.set()
        circ.on_ack_gate.set()
        await controller.stop()


async def test_registry_rename_resolved_before_pump_opening(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    pump, circ = hass.data["p3_fixture"]["outputs"]
    circ.on_ack_gate = asyncio.Event()
    await hass.services.async_call(
        "uninus_nutriculture",
        "start_flow",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    try:
        await asyncio.wait_for(circ.entered_on.wait(), 2)
        er.async_get(hass).async_update_entity(
            pump.entity_id, new_entity_id="switch.renamed_nutrient"
        )
        await asyncio.sleep(0.05)
        circ.on_ack_gate.set()
        await asyncio.wait_for(pump.entered_on.wait(), 1)
        assert pump.entity_id == "switch.renamed_nutrient"
    finally:
        circ.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)
