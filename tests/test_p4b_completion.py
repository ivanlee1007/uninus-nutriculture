"""Parent-resumed P4b acceptance after interrupted workers; no product edits."""

import asyncio
from copy import deepcopy
from datetime import timedelta

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import DAYS, STAGES, prepared, save_v5, until
from test_p4b_native import api, owner
from test_p4b_permit import completed, policy, reports


@pytest.mark.parametrize(
    "kind",
    [
        "sequence_duplicate",
        "sequence_regressed",
        "sequence_bool",
        "sequence_negative",
        "timestamp_future",
        "timestamp_stale",
        "timestamp_naive",
        "timestamp_invalid",
    ],
)
async def test_bad_or_duplicate_report_does_not_qualify(dosing_hass, kind):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    dto = await api(h, ctx, e)
    sources = deepcopy(dto["policy"]["sources"])
    mode = "sequence" if kind.startswith("sequence") else "timestamp"
    for row in sources.values():
        row.update(mode=mode, attribute="measurement", report_contract_confirmed=True)
    await policy(h, e, ctx, sources=sources)
    first_stamp = dt_util.utcnow().isoformat()
    values = [("ph", 5.6, "pH"), ("ec", 0.87, "mS/cm"), ("level", 2.4, "m")]
    for key, value, unit in values:
        h.states.async_set(
            "sensor." + key,
            value,
            {
                "unit_of_measurement": unit,
                "measurement": 5 if mode == "sequence" else first_stamp,
            },
        )
    await h.async_block_till_done()
    assert (await api(h, ctx, e))["quality"]["stable_count"] == 1
    await asyncio.sleep(1.02)
    now = dt_util.utcnow()
    bad = {
        "sequence_duplicate": 5,
        "sequence_regressed": 4,
        "sequence_bool": True,
        "sequence_negative": -1,
        "timestamp_future": (now + timedelta(seconds=60)).isoformat(),
        "timestamp_stale": (now - timedelta(seconds=301)).isoformat(),
        "timestamp_naive": now.replace(tzinfo=None).isoformat(),
        "timestamp_invalid": "not-a-measurement-time",
    }[kind]
    for key, value, unit in values:
        h.states.async_set(
            "sensor." + key,
            value,
            {
                "unit_of_measurement": unit,
                "measurement": bad,
            },
        )
    await h.async_block_till_done()
    actual = await api(h, ctx, e)
    assert actual["permit"]["granted"] is False
    if kind == "sequence_duplicate":
        assert actual["quality"]["stable_count"] == 1
    else:
        assert actual["quality"]["state"] == "invalid", actual
        assert actual["quality"]["stable_count"] == 0
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


async def test_reported_metadata_change_does_not_create_a_round(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    await policy(h, e, ctx)
    await reports(h)
    assert (await api(h, ctx, e))["quality"]["stable_count"] == 1
    await asyncio.sleep(1.02)
    for key in ("ph", "ec", "level"):
        state = h.states.get("sensor." + key)
        h.states.async_set(state.entity_id, state.state, {**state.attributes, "display_only": 1})
    await h.async_block_till_done()
    actual = await api(h, ctx, e)
    assert actual["quality"]["stable_count"] == 1, actual
    assert actual["permit"]["granted"] is False


@pytest.mark.parametrize("kind", ["all_weekdays_skipped", "all_stages_disabled"])
async def test_empty_or_skipped_native_cycle_never_permits(dosing_hass, kind):
    h = dosing_hass
    e, _ = await prepared(h)
    days = {stage: [] if kind == "all_weekdays_skipped" else list(DAYS) for stage in STAGES}
    await save_v5(h, e, weekdays=days)
    ctx = await owner(h)
    await policy(h, e, ctx)
    await reports(h)
    await toggle(h, e, "automation_enabled")
    if kind == "all_weekdays_skipped":
        for stage in STAGES:
            await toggle(h, e, stage + "_enabled")
        # Reach actual refill admission rather than a target-already-satisfied
        # no-op, which correctly has no weekday-start check or started anchor.
        h.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    try:
        await start_native(h, e)
    except ServiceValidationError as err:
        assert kind == "all_stages_disabled", str(err)
    await until(lambda: not e.runtime_data.control.running)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    actual = await api(h, ctx, e)
    assert actual["permit"]["granted"] is False
    assert actual["completion"]["state"] != "completed", actual
    if kind == "all_weekdays_skipped":
        # Started-anchor dependencies may propagate a blocked dependency after
        # the first legitimate weekday skip; this is not stage admission.
        results = [row["result"] for row in e.runtime_data.control.flow.records.values()]
        assert "skipped_weekday" in results
        assert set(results) <= {"skipped_weekday", "blocked_dependency"}
        assert not e.runtime_data.control.flow.times
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


async def test_actual_single_mix_completion_is_not_full_run_permission(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    await policy(h, e, ctx, required_stages=["mix"])
    await reports(h)
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "mix_enabled")
    control = e.runtime_data.control
    clock = control.mix_stage.clock
    control.mix_stage.clock = lambda: clock() * 600
    # Direct existing authenticated Stage.start boundary: there is no registered
    # start_mix domain service. Do not fabricate a full-flow receipt.
    control.run_stage = "mix"
    await control.mix_stage.start(ctx, None)
    await until(lambda: not control.running)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    actual = await api(h, ctx, e)
    assert actual["quality"]["state"] == "qualified", actual
    assert actual["permit"]["granted"] is False
    assert actual["completion"]["state"] == "none"


@pytest.mark.parametrize("route", ["getter", "timer_callback"])
async def test_exact_hard_deadline_backend_clock_boundary(dosing_hass, route):
    h = dosing_hass
    e, ctx = await completed(h)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    q = e.runtime_data.quality
    assert (await api(h, ctx, e))["permit"]["granted"] is True
    cutoff = q.hard
    real_clock = q.clock
    try:
        # Explicit domain-clock seam: this is exact logical boundary evidence,
        # not wall-clock or physical cutoff timing.
        q.clock = lambda: cutoff - 0.000001
        if route == "timer_callback":
            q.expire()
        assert (await api(h, ctx, e))["permit"]["granted"] is True
        q.clock = lambda: cutoff
        if route == "timer_callback":
            q.expire()
        assert (await api(h, ctx, e))["permit"]["granted"] is False
        q.clock = lambda: cutoff + 0.000001
        assert (await api(h, ctx, e))["permit"]["granted"] is False
    finally:
        q.clock = real_clock
    await reports(h)
    assert not (await api(h, ctx, e))["permit"]["granted"]
    assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "off"


async def test_actual_pending_standalone_on_revokes_old_grant(dosing_hass):
    h = dosing_hass
    e, ctx = await completed(h)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    assert (await api(h, ctx, e))["permit"]["granted"] is True
    circ = h.data["p3_fixture"]["outputs"][1]
    circ.entered_on.clear()
    circ.on_ack_gate = asyncio.Event()
    try:
        # Explicit existing standalone Stage.start boundary, not a fabricated
        # full-flow receipt or a nonexistent registered start_mix service.
        e.runtime_data.control.run_stage = "mix"
        await e.runtime_data.control.mix_stage.start(ctx, None)
        await asyncio.wait_for(circ.entered_on.wait(), 3)
        assert not circ.on_ack_gate.is_set()
        assert e.runtime_data.control.running
        assert (await api(h, ctx, e))["permit"]["granted"] is False
        assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "off"
    finally:
        circ.on_ack_gate.set()
        await asyncio.wait_for(toggle(h, e, "flow_run", False), 8)
    assert (await api(h, ctx, e))["permit"]["granted"] is False


async def test_unrelated_registry_creation_during_run_does_not_consume_receipt(dosing_hass):
    from homeassistant.helpers import entity_registry as er

    h = dosing_hass
    task = asyncio.create_task(completed(h))
    try:

        def active_entry():
            entries = h.config_entries.async_entries("uninus_nutriculture")
            return next(
                (
                    e
                    for e in entries
                    if getattr(e, "runtime_data", None)
                    and e.runtime_data.quality.completion["state"] == "running"
                ),
                None,
            )

        await until(lambda: active_entry() is not None)
        e = active_entry()
        before_epoch = e.runtime_data.quality.epoch
        registry = er.async_get(h)
        row = registry.async_get_or_create(
            "sensor",
            "test",
            "p4b_unrelated_registry_entry",
            suggested_object_id="p4b_unrelated_registry_entry",
        )
        assert row.config_entry_id is None
        await asyncio.sleep(0.03)
        after_epoch = e.runtime_data.quality.epoch
        e, ctx = await task
        await reports(h)
        await asyncio.sleep(1.02)
        await reports(h)
        actual = await api(h, ctx, e)
        assert actual["permit"]["granted"] is True, {
            "dto": actual,
            "before_epoch": before_epoch,
            "after_epoch": after_epoch,
            "unrelated_registry_entity": row.entity_id,
        }
        assert before_epoch == after_epoch
    finally:
        if not task.done():
            await asyncio.wait_for(task, 15)


async def test_real_reload_does_not_restore_grant_and_old_callback_isolated(dosing_hass):
    h = dosing_hass
    e, ctx = await completed(h)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    previous = await api(h, ctx, e)
    assert previous["permit"]["granted"] is True
    old_quality = e.runtime_data.quality
    old_epoch = old_quality.epoch
    saved_policy = deepcopy(e.options["quality_policy"])
    assert await h.config_entries.async_reload(e.entry_id)
    actual = await api(h, ctx, e)
    assert e.options["quality_policy"] == saved_policy
    assert actual["epoch"] != old_epoch
    assert actual["completion"]["state"] == "none"
    assert actual["quality"]["stable_count"] == 0
    assert actual["permit"]["granted"] is False
    assert old_quality.closed is True
    # Explicitly execute the old retired callback; no new epoch may be changed.
    clock = old_quality.clock
    old_quality.clock = lambda: clock() + 1000
    old_quality.expire()
    after = await api(h, ctx, e)
    assert after["epoch"] == actual["epoch"]
    assert after["quality"]["stable_count"] == 0
    assert after["permit"]["granted"] is False
