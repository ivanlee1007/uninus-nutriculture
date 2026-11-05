"""Event-only count, independent duration and closed policy validation."""

import asyncio
from copy import deepcopy

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5
from test_p4b_native import api, owner
from test_p4b_permit import policy, reports


async def test_no_run_count_duration_polling(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    await policy(h, e, ctx, stable_samples=2, stable_duration_seconds=2)
    await reports(h)
    for _ in range(10):
        d = await api(h, ctx, e)
        assert d["quality"]["stable_count"] == 1
    await asyncio.sleep(1.02)
    await reports(h)
    d = await api(h, ctx, e)
    assert d["quality"]["stable_count"] == 2 and d["quality"]["state"] == "stabilizing"
    await asyncio.sleep(1.02)
    await reports(h)
    d = await api(h, ctx, e)
    assert d["quality"]["state"] == "qualified" and d["quality"]["stable_count"] == 2
    assert not d["permit"]["granted"] and d["completion"]["state"] == "none"


@pytest.mark.parametrize(
    "bad", ["extra", "bool", "empty", "unconfirmed", "attribute", "unknownschema"]
)
async def test_policy_closed_atomic(dosing_hass, bad):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    d = await api(h, ctx, e)
    p = deepcopy(d["policy"])
    if bad == "extra":
        p["extra"] = 1
    elif bad == "bool":
        p["stable_samples"] = True
    elif bad == "empty":
        p["required_stages"] = []
    elif bad == "unconfirmed":
        p["enabled"] = True
    elif bad == "attribute":
        p["sources"]["ph"]["attribute"] = "x"
    else:
        h.config_entries.async_update_entry(
            e, options={**e.options, "quality_policy": {"schema_version": 99}}
        )
    before = deepcopy(dict(e.options))
    with pytest.raises(ServiceValidationError):
        await api(
            h,
            ctx,
            e,
            "save_quality_policy_v1",
            expected_policy_revision=0,
            expected_settings_revision=d["settings_revision"],
            expected_flow_plan_revision=d["flow_plan_revision"],
            policy=p,
        )
    assert dict(e.options) == before


async def test_stabilization_freshness_callback_without_getter(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    async with e.runtime_data.lock:
        e.runtime_data.write_settings(sources={**e.runtime_data.sources, "max_age_seconds": 10})
    await policy(h, e, ctx, stable_samples=2, stable_duration_seconds=20)
    await reports(h)
    from test_p2_control import target

    identity = target(h, e, "sensor", "quality_status")
    assert h.states.get(identity).attributes["quality"]["stable_count"] == 1
    await asyncio.sleep(10.05)
    state = h.states.get(identity)
    assert state.attributes["quality"]["stable_count"] == 0
    assert state.attributes["quality"]["state"] == "invalid"
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
