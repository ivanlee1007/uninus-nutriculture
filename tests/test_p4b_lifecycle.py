"""Native mutations and source invalidation, never restore old receipts."""

import asyncio
from copy import deepcopy

import pytest
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5, until
from test_p4b_native import api, owner
from test_p4b_permit import completed, policy, reports


@pytest.mark.parametrize(
    "mutation", ["same_apply", "number", "policy", "source", "master", "unload"]
)
async def test_native_grant_mutation_consumes(dosing_hass, mutation):
    h = dosing_hass
    e, ctx = await completed(h, recipe=mutation == "same_apply")
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    assert (await api(h, ctx, e))["permit"]["granted"]
    if mutation == "same_apply":
        from test_p4a_recipes import call

        h.data["recipe_context"] = ctx
        d = await call(
            h,
            "save_recipe_v1",
            dict(
                config_entry_id=e.entry_id,
                expected_catalog_revision=e.options["recipe_catalog"]["revision"],
                recipe_id=e.options["recipe_catalog"]["recipes"][0]["id"],
                name="same",
                parameters=dict(e.runtime_data.parameters),
            ),
        )
        assert (await api(h, ctx, e))["permit"]["granted"], "catalog Save must not revoke"
        await call(
            h,
            "apply_recipe_v1",
            dict(
                config_entry_id=e.entry_id,
                expected_catalog_revision=d["catalog_revision"],
                expected_settings_revision=d["settings_revision"],
                recipe_id=d["recipes"][0]["id"],
            ),
        )
    elif mutation == "number":
        await h.services.async_call(
            "number",
            "set_value",
            {"entity_id": target(h, e, "number", "ph_high"), "value": 5.9},
            blocking=True,
        )
    elif mutation == "policy":
        await policy(h, e, ctx)
    elif mutation == "source":
        h.states.async_set("sensor.ec", "unavailable", {"unit_of_measurement": "mS/cm"})
        await h.async_block_till_done()
    elif mutation == "master":
        await toggle(h, e, "automation_enabled", False)
    elif mutation == "unload":
        q = e.runtime_data.quality
        assert await h.config_entries.async_unload(e.entry_id)
        assert q.closed and q.timer is None and not q.granted and not q.unsubs
        return
    assert not (await api(h, ctx, e))["permit"]["granted"], mutation
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    assert not (await api(h, ctx, e))["permit"]["granted"]


async def test_acl_revoked_while_waiting_and_three_cas(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    d = await api(h, ctx, e)
    before = deepcopy(dict(e.options))
    payload = dict(
        expected_policy_revision=0,
        expected_settings_revision=d["settings_revision"],
        expected_flow_plan_revision=d["flow_plan_revision"],
        policy=d["policy"],
    )
    for key in (
        "expected_policy_revision",
        "expected_settings_revision",
        "expected_flow_plan_revision",
    ):
        with pytest.raises(ServiceValidationError, match="quality_conflict"):
            await api(h, ctx, e, "save_quality_policy_v1", **{**payload, key: payload[key] + 1})
        assert dict(e.options) == before
    await e.runtime_data.lock.acquire()
    task = asyncio.create_task(api(h, ctx, e, "save_quality_policy_v1", **payload))
    await until(lambda: bool(e.runtime_data.lock._waiters))
    user = await h.auth.async_get_user(ctx.user_id)
    user.is_active = False
    e.runtime_data.lock.release()
    with pytest.raises(Unauthorized):
        await task
    assert dict(e.options) == before
