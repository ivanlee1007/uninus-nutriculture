"""Additional captured-event and source-contract counterexamples."""

import asyncio
from copy import deepcopy

import pytest
from homeassistant.util import dt as dt_util
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import DAYS, STAGES, plan, prepared, save_v5, until
from test_p4b_native import api, owner
from test_p4b_permit import completed, policy, reports


async def test_captured_output_on_off_same_tick_consumes(dosing_hass):
    h = dosing_hass
    e, ctx = await completed(h)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    assert (await api(h, ctx, e))["permit"]["granted"]
    pump = h.data["p3_fixture"]["outputs"][0]
    h.states.async_set(pump.entity_id, "on")
    h.states.async_set(pump.entity_id, "off")
    await h.async_block_till_done()
    assert not (await api(h, ctx, e))["permit"]["granted"]


@pytest.mark.parametrize("mode", ["sequence", "timestamp"])
async def test_changed_sample_contract_resets_old_token_fence(dosing_hass, mode):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    await policy(h, e, ctx)
    await reports(h)
    d = await api(h, ctx, e)
    sources = deepcopy(d["policy"]["sources"])
    for row in sources.values():
        row.update(mode=mode, attribute="measurement")
    await policy(h, e, ctx, sources=sources)
    for seq in (1, 2):
        for k, v, u in [("ph", 5.6, "pH"), ("ec", 0.87, "mS/cm"), ("level", 2.4, "m")]:
            token = seq if mode == "sequence" else dt_util.utcnow().isoformat()
            h.states.async_set("sensor." + k, v, {"unit_of_measurement": u, "measurement": token})
        await h.async_block_till_done()
        if seq == 1:
            await asyncio.sleep(1.02)
    d = await api(h, ctx, e)
    assert d["quality"]["state"] == "qualified", d
    assert not d["permit"]["granted"]


@pytest.mark.parametrize("kind", ["required_disabled", "enabled_weekday_skip", "mix_subset"])
async def test_actual_native_mix_subset_and_denied_receipts(dosing_hass, kind):
    h = dosing_hass
    e, _ = await prepared(h)
    p = plan()
    for row in p["rows"]:
        row.update(start_rule="flow_start", delay_seconds=0)
    days = {s: list(DAYS) for s in STAGES}
    if kind == "enabled_weekday_skip":
        days["mix"] = []
    await save_v5(h, e, p, days)
    ctx = await owner(h)
    await policy(h, e, ctx, required_stages=["refill"] if kind == "required_disabled" else ["mix"])
    h.states.async_set("sensor.level", 2.4, {"unit_of_measurement": "m"})
    h.states.async_set("sensor.ph", 5.6, {"unit_of_measurement": "pH"})
    h.states.async_set("sensor.ec", 0.87, {"unit_of_measurement": "mS/cm"})
    await h.async_block_till_done()
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "mix_enabled")
    c = e.runtime_data.control
    clock = c.mix_stage.clock
    c.mix_stage.clock = lambda: clock() * 600
    await start_native(h, e)
    await until(lambda: not c.running)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    d = await api(h, ctx, e)
    assert d["permit"]["granted"] is (kind == "mix_subset"), d
    if kind != "mix_subset":
        assert d["completion"]["state"] == "incomplete"


async def test_native_permit_registry_loss_revokes_authority(dosing_hass):
    from homeassistant.helpers import entity_registry as er
    from test_p2_control import target

    h = dosing_hass
    e, ctx = await completed(h)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    assert (await api(h, ctx, e))["permit"]["granted"]
    identity = target(h, e, "binary_sensor", "irrigation_permit")
    er.async_get(h).async_remove(identity)
    await h.async_block_till_done()
    d = await api(h, ctx, e)
    assert d["entities"]["irrigation_permit"] is None
    assert d["permit"]["granted"] is False
