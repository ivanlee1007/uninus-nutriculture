"""Recipe boundary probes; registered services and actual principal manager."""

import asyncio
from copy import deepcopy

import pytest
from homeassistant.auth import auth_manager_from_config
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from test_p2_control import add_tank
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5, until


async def setup(hass):
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    hass.auth = await auth_manager_from_config(hass, [], [])
    await hass.auth.async_create_user("owner")
    user = await hass.auth.async_create_user("admin", group_ids=["system-admin"])
    return entry, Context(user_id=user.id), user


async def rpc(hass, entry, context, service, **fields):
    return await hass.services.async_call(
        "uninus_nutriculture",
        service,
        {"config_entry_id": entry.entry_id, **fields},
        context=context,
        blocking=True,
        return_response=True,
    )


async def saved(hass, entry, context):
    return await rpc(
        hass,
        entry,
        context,
        "save_recipe_v1",
        expected_catalog_revision=0,
        recipe_id=None,
        name="same",
        parameters={**entry.runtime_data.parameters, "ph_high": 5.9},
    )


@pytest.mark.parametrize(
    "bad", ["bool", "nan", "infinity", "extra", "missing", "pair", "name", "nested"]
)
async def test_invalid_save_atomic(dosing_hass, bad):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    p = dict(e.runtime_data.parameters)
    name = "OK"
    if bad == "bool":
        p["ph_high"] = True
    elif bad == "nan":
        p["ph_high"] = float("nan")
    elif bad == "infinity":
        p["ph_high"] = float("inf")
    elif bad == "extra":
        p["extra"] = 1
    elif bad == "missing":
        del p["ph_high"]
    elif bad == "pair":
        p["ph_high"] = p["ph_low"]
    elif bad == "name":
        name = "bad\x00"
    else:
        p["ph_high"] = {}
    before = deepcopy(dict(e.options))
    with pytest.raises(ServiceValidationError, match="invalid_recipe"):
        await rpc(
            h,
            e,
            ctx,
            "save_recipe_v1",
            expected_catalog_revision=0,
            recipe_id=None,
            name=name,
            parameters=p,
        )
    assert dict(e.options) == before
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


async def test_noop_cas_history_manual_number_and_two_tanks(dosing_hass):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    d = await saved(h, e, ctx)
    r = d["recipes"][0]
    assert (
        await rpc(
            h,
            e,
            ctx,
            "save_recipe_v1",
            expected_catalog_revision=1,
            recipe_id=r["id"],
            name=r["name"],
            parameters=r["parameters"],
        )
    ) == d
    for service, fields, code in [
        (
            "save_recipe_v1",
            dict(
                expected_catalog_revision=0,
                recipe_id=r["id"],
                name="bad",
                parameters=r["parameters"],
            ),
            "recipe_conflict",
        ),
        (
            "apply_recipe_v1",
            dict(expected_catalog_revision=1, expected_settings_revision=999, recipe_id=r["id"]),
            "settings_conflict",
        ),
        (
            "delete_recipe_v1",
            dict(expected_catalog_revision=1, recipe_id=r["id"], confirm_delete=1),
            "confirmation_required",
        ),
    ]:
        before = deepcopy(dict(e.options))
        with pytest.raises(ServiceValidationError, match=code):
            await rpc(h, e, ctx, service, **fields)
        assert dict(e.options) == before
    d = await rpc(
        h,
        e,
        ctx,
        "apply_recipe_v1",
        expected_catalog_revision=1,
        expected_settings_revision=d["settings_revision"],
        recipe_id=r["id"],
    )
    again = await rpc(
        h,
        e,
        ctx,
        "apply_recipe_v1",
        expected_catalog_revision=d["catalog_revision"],
        expected_settings_revision=d["settings_revision"],
        recipe_id=r["id"],
    )
    assert again == d
    from test_p2_control import target

    await h.services.async_call(
        "number",
        "set_value",
        {"entity_id": target(h, e, "number", "ph_high"), "value": 6.0},
        blocking=True,
    )
    now = await rpc(h, e, ctx, "get_recipes_v1")
    assert now["parameters_match"] is False and now["last_applied"] == d["last_applied"]
    other = await add_tank(h)
    before = deepcopy(dict(other.options))
    with pytest.raises(ServiceValidationError, match="settings_schema_mismatch"):
        await rpc(h, other, ctx, "get_recipes_v1")
    assert dict(other.options) == before


@pytest.mark.parametrize("kind", ["revoked", "inactive_runtime", "replaced_runtime"])
async def test_after_lock_denial(dosing_hass, kind):
    h = dosing_hass
    e, ctx, user = await setup(h)
    old = e.runtime_data
    before = deepcopy(dict(e.options))
    await old.lock.acquire()
    task = asyncio.create_task(saved(h, e, ctx))
    try:
        await until(lambda: bool(old.lock._waiters))
        if kind == "revoked":
            await h.auth.async_update_user(user, is_active=False)
        elif kind == "inactive_runtime":
            old.active = False
        else:
            e.runtime_data = object()
    finally:
        old.lock.release()
    try:
        with pytest.raises((Unauthorized, ServiceValidationError)):
            await task
        assert dict(e.options) == before
    finally:
        e.runtime_data = old
        old.active = True


async def test_apply_rejects_queued_tank_owner(dosing_hass):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    d = await saved(h, e, ctx)
    tank = e.runtime_data
    before = deepcopy(dict(e.options))
    await tank.lock.acquire()
    apply = asyncio.create_task(
        rpc(
            h,
            e,
            ctx,
            "apply_recipe_v1",
            expected_catalog_revision=1,
            expected_settings_revision=d["settings_revision"],
            recipe_id=d["recipes"][0]["id"],
        )
    )
    await until(lambda: bool(tank.lock._waiters))
    entered = asyncio.Event()

    async def queued_owner():
        async with tank.lock:
            entered.set()

    owner = asyncio.create_task(queued_owner())
    await until(lambda: len(tank.lock._waiters) == 2)
    tank.lock.release()
    try:
        with pytest.raises(ServiceValidationError, match="busy"):
            await apply
        assert dict(e.options) == before
    finally:
        await owner
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
