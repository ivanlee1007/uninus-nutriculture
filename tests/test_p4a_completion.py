"""Remaining frozen P4a cells, native transport and existing hardware seams."""

import asyncio
from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from test_p2_control import add_tank, target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import plan, save_v5, until
from test_p4a_recipes_boundaries import rpc, saved, setup

SERVICES = ("get_recipes_v1", "save_recipe_v1", "delete_recipe_v1", "apply_recipe_v1")


def fields(service, dto):
    if service == "get_recipes_v1":
        return {}
    record = dto["recipes"][0]
    data = dict(expected_catalog_revision=dto["catalog_revision"], recipe_id=record["id"])
    if service == "save_recipe_v1":
        data.update(name="changed", parameters=record["parameters"])
    elif service == "delete_recipe_v1":
        data["confirm_delete"] = True
    else:
        data["expected_settings_revision"] = dto["settings_revision"]
    return data


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("denial", ["nonadmin", "revoked"])
async def test_initial_acl_before_lookup_and_catalog(dosing_hass, service, denial):
    h = dosing_hass
    e, ctx, admin = await setup(h)
    d = await saved(h, e, ctx)
    data = fields(service, d)
    if denial == "nonadmin":
        user = await h.auth.async_create_user("ordinary", group_ids=["system-users"])
        ctx = Context(user_id=user.id)
    else:
        await h.auth.async_update_user(admin, is_active=False)
    before = deepcopy(dict(e.options))
    from custom_components.uninus_nutriculture import recipes

    with (
        patch.object(
            h.config_entries, "async_get_entry", side_effect=AssertionError("lookup")
        ) as lookup,
        patch.object(recipes, "catalog", side_effect=AssertionError("protected read")) as read,
    ):
        with pytest.raises(Unauthorized):
            await rpc(h, e, ctx, service, **data)
        lookup.assert_not_called()
        read.assert_not_called()
    assert dict(e.options) == before
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


@pytest.mark.parametrize("service", SERVICES)
async def test_all_services_recheck_revocation_after_lock(dosing_hass, service):
    h = dosing_hass
    e, ctx, admin = await setup(h)
    d = await saved(h, e, ctx)
    before = deepcopy(dict(e.options))
    from custom_components.uninus_nutriculture import recipes

    async with e.runtime_data.lock:
        task = asyncio.create_task(rpc(h, e, ctx, service, **fields(service, d)))
        await until(lambda: bool(e.runtime_data.lock._waiters))
        await h.auth.async_update_user(admin, group_ids=["system-users"])
    with patch.object(recipes, "catalog", side_effect=AssertionError("protected read")) as read:
        with pytest.raises(Unauthorized):
            await task
        read.assert_not_called()
    assert dict(e.options) == before


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("state", ["disabled", "unloaded"])
async def test_all_services_entry_lifecycle_rejected(dosing_hass, service, state):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    d = await saved(h, e, ctx)
    if state == "disabled":
        await h.config_entries.async_set_disabled_by(e.entry_id, ConfigEntryDisabler.USER)
    else:
        assert await h.config_entries.async_unload(e.entry_id)
    before = deepcopy(dict(e.options))
    with pytest.raises(ServiceValidationError, match="^entry_not_loaded$"):
        await rpc(h, e, ctx, service, **fields(service, d))
    assert dict(e.options) == before


async def test_two_v5_slots_same_name_cross_id_and_cas_isolation(dosing_hass):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    other = await add_tank(h)
    flow = await h.config_entries.options.async_init(other.entry_id)
    result = await h.config_entries.options.async_configure(
        flow["flow_id"],
        {
            **{k: other.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            "commissioned": False,
        },
    )
    assert result["type"] == "create_entry", result
    await save_v5(h, other)
    assert other.options["control_contract_version"] == 5
    assert not other.options.get("control", {}).get("commissioned", False)
    a = await saved(h, e, ctx)
    b = await saved(h, other, ctx)
    assert a["recipes"][0]["name"] == b["recipes"][0]["name"]
    assert a["recipes"][0]["id"] != b["recipes"][0]["id"]
    baseline = [deepcopy(dict(x.options)) for x in (e, other)]
    for service in SERVICES[1:]:
        data = fields(service, b)
        data["recipe_id"] = a["recipes"][0]["id"]
        with pytest.raises(ServiceValidationError, match="^recipe_not_found$"):
            await rpc(h, other, ctx, service, **data)
        assert [dict(x.options) for x in (e, other)] == baseline
    data = fields("save_recipe_v1", a)
    data["name"] = "renamed"
    a2 = await rpc(h, e, ctx, "save_recipe_v1", **data)
    assert a2["recipes"][0]["id"] == a["recipes"][0]["id"]
    assert await rpc(h, other, ctx, "get_recipes_v1") == b
    with pytest.raises(ServiceValidationError, match="^recipe_conflict$"):
        await rpc(h, e, ctx, "delete_recipe_v1", **fields("delete_recipe_v1", a))
    assert await rpc(h, other, ctx, "get_recipes_v1") == b
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


async def test_native_hundredth_and_exact_101_limit_zero_write(dosing_hass):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    for revision in range(100):
        d = await rpc(
            h,
            e,
            ctx,
            "save_recipe_v1",
            expected_catalog_revision=revision,
            recipe_id=None,
            name="same",
            parameters=dict(e.runtime_data.parameters),
        )
        assert d["catalog_revision"] == revision + 1
        assert len(d["recipes"]) == revision + 1
    before = deepcopy(dict(e.options))
    with pytest.raises(ServiceValidationError, match="^recipe_limit$"):
        await rpc(
            h,
            e,
            ctx,
            "save_recipe_v1",
            expected_catalog_revision=100,
            recipe_id=None,
            name="101",
            parameters=dict(e.runtime_data.parameters),
        )
    assert dict(e.options) == before
    assert len({r["id"] for r in d["recipes"]}) == 100
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


@pytest.mark.parametrize("role", ["refill", "nutrient", "acid", "mix"])
async def test_apply_actual_role_pending_io_preserves_accepted_plan(dosing_hass, role):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    p = plan()
    order = [role] + [s for s in ("refill", "nutrient", "acid", "mix") if s != role]
    for index, row in enumerate(p["rows"]):
        row.update(
            stage=order[index],
            start_rule="flow_start" if index == 0 else "after_previous_finished",
            delay_seconds=0,
        )
    await save_v5(h, e, p)
    d = await saved(h, e, ctx)
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, role + "_enabled")
    c = e.runtime_data.control
    hardware = (
        h.data["p2_fixture"]["hardware"]
        if role == "refill"
        else h.data["p3_fixture"]["outputs"][1]
        if role in ("nutrient", "mix")
        else None
    )
    # Acid uses the prepared fixture's registered Acid output, held at the owned dispatch seam.
    entered, release = asyncio.Event(), asyncio.Event()
    original = c.nutrient_dispatch

    async def held(r, enabled, **kwargs):
        if enabled:
            entered.set()
            await release.wait()
        return await original(r, enabled, **kwargs)

    if role == "refill":
        hardware.on_ack_gate = release
    else:
        c.nutrient_dispatch = held
    if role in ("acid", "nutrient", "mix"):
        h.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await start_native(h, e)
    try:
        if role == "refill":
            await until(lambda: hardware.is_on)
        else:
            await asyncio.wait_for(entered.wait(), 3)
        assert c.running
        if role != "refill":
            assert getattr(c, role + "_stage").owns_io
        accepted = deepcopy(c.flow.run_plan)
        before = deepcopy(dict(e.options))
        calls = deepcopy((h.data["p2_fixture"]["calls"], h.data["p3_fixture"]["calls"]))
        with pytest.raises(ServiceValidationError, match="^busy$"):
            await rpc(h, e, ctx, "apply_recipe_v1", **fields("apply_recipe_v1", d))
        assert dict(e.options) == before and c.flow.run_plan == accepted
        assert (h.data["p2_fixture"]["calls"], h.data["p3_fixture"]["calls"]) == calls
    finally:
        release.set()
        await toggle(h, e, "flow_run", False)


async def test_apply_lease_and_admission_lock_busy_then_fault_settled_data_only(dosing_hass):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    d = await saved(h, e, ctx)
    c = e.runtime_data.control
    before = deepcopy(dict(e.options))
    token = c.acquire("owned-completion-session", "run", c.generation, "mix")
    try:
        assert not c.running and c.leases
        with pytest.raises(ServiceValidationError, match="^busy$"):
            await rpc(h, e, ctx, "apply_recipe_v1", **fields("apply_recipe_v1", d))
        assert dict(e.options) == before
    finally:
        c.release(token)
    async with c.lock:
        with pytest.raises(ServiceValidationError, match="^busy$"):
            await rpc(h, e, ctx, "apply_recipe_v1", **fields("apply_recipe_v1", d))
        assert dict(e.options) == before
    await h.services.async_call(
        "button", "press", {"entity_id": target(h, e, "button", "emergency_stop")}, blocking=True
    )
    assert c.fault == "emergency_stop" and not c.running and not c.leases
    before = deepcopy(dict(e.options))
    calls = deepcopy((h.data["p2_fixture"]["calls"], h.data["p3_fixture"]["calls"]))
    enabled = (c.master, c.refill, c.nutrient, c.acid, c.mix)
    result = await rpc(h, e, ctx, "apply_recipe_v1", **fields("apply_recipe_v1", d))
    assert result["parameters_match"] is True
    assert c.fault == "emergency_stop" and enabled == (
        c.master,
        c.refill,
        c.nutrient,
        c.acid,
        c.mix,
    )
    assert (h.data["p2_fixture"]["calls"], h.data["p3_fixture"]["calls"]) == calls
    status = h.states.get(target(h, e, "sensor", "control_status"))
    assert status.attributes["ready_for_irrigation"] is False
    for key in before.keys() - {"parameters", "recipe_catalog", "settings_revision"}:
        assert e.options[key] == before[key]


async def test_ordinary_options_and_number_keep_catalog_noop_revision(dosing_hass):
    h = dosing_hass
    e, ctx, _ = await setup(h)
    d = await saved(h, e, ctx)
    d = await rpc(h, e, ctx, "apply_recipe_v1", **fields("apply_recipe_v1", d))
    catalog = deepcopy(e.options["recipe_catalog"])
    for value in (5.9, 6.0, 6.0):
        before = e.options["settings_revision"]
        old = e.runtime_data.parameters["ph_high"]
        await h.services.async_call(
            "number",
            "set_value",
            {"entity_id": target(h, e, "number", "ph_high"), "value": value},
            blocking=True,
        )
        assert e.options["settings_revision"] == before + (old != value)
        assert e.options["recipe_catalog"] == catalog
    for age in (301, 301):
        before = e.options["settings_revision"]
        old = e.options.get("max_age_seconds", e.data["max_age_seconds"])
        flow = await h.config_entries.options.async_init(
            e.entry_id, context={"user_id": ctx.user_id}
        )
        values = {
            str(k): k.description["suggested_value"]
            for k in flow["data_schema"].schema
            if k.description
            and "suggested_value" in k.description
            and k.description["suggested_value"] is not None
        }
        result = await h.config_entries.options.async_configure(
            flow["flow_id"],
            {**values, **{k: e.data[k] for k in ("ph", "ec", "level")}, "max_age_seconds": age},
        )
        assert result["type"] == "create_entry", result
        assert e.options["recipe_catalog"] == catalog
        assert e.options["settings_revision"] == before + (old != age)
    now = await rpc(h, e, ctx, "get_recipes_v1")
    assert now["parameters_match"] is False and now["last_applied"] == d["last_applied"]
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
