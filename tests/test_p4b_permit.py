"""Actual Core full four-stage closure -> new reports -> permit tracer."""

import asyncio
from copy import deepcopy

from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import STAGES, prepared, save_v5, until
from test_p4b_native import api, owner


async def policy(h, e, ctx, **changes):
    d = await api(h, ctx, e)
    p = deepcopy(d["policy"])
    p.update(
        enabled=True,
        stable_samples=2,
        stable_interval_seconds=1,
        stable_duration_seconds=1,
        permit_ttl_seconds=2,
    )
    p.update(changes)
    for row in p["sources"].values():
        row["report_contract_confirmed"] = True
    return await api(
        h,
        ctx,
        e,
        "save_quality_policy_v1",
        expected_policy_revision=d["policy_revision"],
        expected_settings_revision=d["settings_revision"],
        expected_flow_plan_revision=d["flow_plan_revision"],
        policy=p,
    )


async def reports(h):
    for k, v, u in [("ph", 5.6, "pH"), ("ec", 0.87, "mS/cm"), ("level", 2.4, "m")]:
        h.states.async_set("sensor." + k, v, {"unit_of_measurement": u})
        # A genuine second identical device report emits state_reported, unlike metadata changes.
        h.states.async_set("sensor." + k, v, {"unit_of_measurement": u})
    await h.async_block_till_done()


async def completed(h, recipe=False):
    e, acid = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    await policy(h, e, ctx)
    if recipe:
        from test_p4a_recipes import call

        h.data["recipe_context"] = ctx
        d = await call(
            h,
            "save_recipe_v1",
            dict(
                config_entry_id=e.entry_id,
                expected_catalog_revision=0,
                recipe_id=None,
                name="same",
                parameters=dict(e.runtime_data.parameters),
            ),
        )
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
    await toggle(h, e, "automation_enabled")
    for s in STAGES:
        await toggle(h, e, s + "_enabled")
    c = e.runtime_data.control
    real = c.mix_stage.clock
    c.mix_stage.clock = lambda: real() * 600  # explicit legal domain-time acceleration
    await start_native(h, e)
    pump, circ = h.data["p3_fixture"]["outputs"]
    refill = h.data["p2_fixture"]["hardware"]
    await until(lambda: refill.is_on)
    h.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await asyncio.wait_for(circ.entered_on.wait(), 3)
    await until(lambda: c.flow.records["mix"]["result"] == "completed")
    h.states.async_set("sensor.level", "2.4", {"unit_of_measurement": "m"})
    await asyncio.wait_for(pump.entered_on.wait(), 3)
    h.states.async_set("sensor.ec", ".86", {"unit_of_measurement": "mS/cm"})
    await until(lambda: c.nutrient_stage.phase == "waiting_sample")
    h.states.async_set("sensor.ec", ".87", {"unit_of_measurement": "mS/cm"})
    await asyncio.wait_for(acid.entered_on.wait(), 3)
    h.states.async_set("sensor.ph", "5.6", {"sample": 2})
    await until(lambda: c.acid_stage.phase == "waiting_sample")
    h.states.async_set("sensor.ph", "5.6", {"sample": 3})
    await until(lambda: not c.running)
    assert c.flow.outcome == "completed" and c.fault is None
    assert all(r["result"] == "completed" for r in c.flow.records.values())
    assert not any(x.is_on for x in (pump, circ, refill, acid)) and not c.leases
    return e, ctx


async def test_full_flow_new_reports_grant_then_deadline_never_revives(dosing_hass):
    h = dosing_hass
    e, ctx = await completed(h)
    try:
        assert not (await api(h, ctx, e))["permit"]["granted"]
        await reports(h)
        await asyncio.sleep(1.02)
        await reports(h)
        d = await api(h, ctx, e)
        print(
            "QUALITY_DTO",
            d,
            "CONSUMED",
            e.runtime_data.quality.consumed,
            "TOKENS",
            e.runtime_data.quality.tokens,
            "USED",
            e.runtime_data.quality.used,
        )
        assert d["permit"]["granted"] is True, d
        assert d["quality"]["state"] == "qualified"
        assert d["completion"]["state"] == "completed"
        assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "on"
        old = h.states.get(target(h, e, "sensor", "control_status"))
        assert old.attributes["ready_for_irrigation"] is False
        await asyncio.sleep(1.0)
        await reports(h)  # freshness refresh cannot extend the hard grant TTL
        await asyncio.sleep(1.05)
        assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "off"
        await reports(h)
        assert not (await api(h, ctx, e))["permit"]["granted"]
    finally:
        await toggle(h, e, "flow_run", False)
