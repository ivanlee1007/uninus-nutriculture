"""Fault notification correlation on native Core; no controller replacements."""

from copy import deepcopy

import pytest
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import plan, prepared, save_v5, until
from test_p4c_completion import policy
from test_p4c_notifications import connection


async def accepted_runtime(h):
    e, _ = await prepared(h)
    p = plan()
    # Controlled fixture: keep all stages in delay, outside the known baseline
    # MixStage.deadline initialization callback window. This does NOT repair P3.
    for row in p["rows"]:
        row.update(start_rule="flow_start", delay_seconds=15)
    await save_v5(h, e, p)
    # Controlled baseline isolation ONLY: emergency ownership can call tighten
    # before MixStage.start initializes deadline. Seed that instance's deadline;
    # native callbacks, STOP routing, OFF and result observation stay unmodified.
    # This regression is not acceptance of the separate P3 initialization defect.
    mix = e.runtime_data.control.mix_stage
    mix.started = mix.clock()
    mix.deadline = mix.started + 1200
    mix.end = mix.started + e.runtime_data.parameters["mix_duration"] * 60
    conn, replies = await connection(h)
    await policy(conn, replies, e, events=["danger", "timeout", "stop_unconfirmed", "failed"])
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "refill_enabled")
    response = await start_native(h, e)
    assert response["accepted"] is True
    run = e.runtime_data.results.dto()["current_run"]
    assert run is not None and run["run_id"] == response["run_id"]
    return e, e.runtime_data.notifications, conn, replies


async def test_native_resolved_alarm_does_not_swallow_emergency_failure(dosing_hass, caplog):
    h = dosing_hass
    e, n, _, _ = await accepted_runtime(h)
    events = []

    @callback
    def seen(event):
        events.append(deepcopy(dict(event.data)))

    unsub = h.bus.async_listen("uninus_nutriculture_result_v1", seen)
    try:
        h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
        await until(lambda: n.deliveries and n.deliveries[0]["status"] == "handoff_returned")
        h.states.async_set("sensor.ph", "5.6", {"unit_of_measurement": "pH"})
        await until(lambda: e.runtime_data.results.alarms["ph_low"][1] is False)
        # Drain real native source callbacks before entering emergency ownership.
        # Do not replace callbacks or suppress their diagnostics.
        await h.async_block_till_done()
        buttons = [
            row.entity_id
            for row in er.async_get(h).entities.values()
            if row.config_entry_id == e.entry_id
            and row.domain == "button"
            and "stop" in row.unique_id
        ]
        assert len(buttons) == 1
        await h.services.async_call("button", "press", {"entity_id": buttons[0]}, blocking=True)
        await until(lambda: e.runtime_data.results.dto()["last_result"] is not None)
        await h.async_block_till_done()
        failed = e.runtime_data.results.dto()["last_result"]
        assert (failed["state"], failed["reason"], failed["closure"]) == (
            "failed",
            "emergency_stop",
            "confirmed",
        )
        assert any(event["kind"] == "failed" and event["run"] == failed for event in events)
        assert not h.data["p2_fixture"]["hardware"].is_on
        assert not e.runtime_data.control.leases
        assert not [row.getMessage() for row in caplog.records if row.levelname == "ERROR"]
        assert any(
            row["kind"] == "failed" and row["status"] == "handoff_returned" for row in n.deliveries
        ), n.dto()
    finally:
        unsub()


async def observed_event(e, kind, why, run=None):
    """Controlled observer-stream seam; actual dispatcher and native provider."""
    from homeassistant.util import dt as dt_util

    r = e.runtime_data.results
    r.event(kind, why, run or r.dto()["current_run"], dt_util.utcnow().isoformat())
    return r.dto()["latest_event"]


async def test_same_alarm_episode_is_merged_without_dangling_queued_record(dosing_hass):
    h = dosing_hass
    e, n, _, _ = await accepted_runtime(h)
    h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
    await until(lambda: n.deliveries and n.deliveries[0]["status"] == "handoff_returned")
    event = await observed_event(e, "failed", "ph_danger")
    await until(lambda: n.dispatcher.worker.done())
    assert all(row["event_id"] != event["event_id"] for row in n.deliveries)
    assert not n.dispatcher.queue


@pytest.mark.parametrize("boundary", ["recovered", "recurrence", "policy", "other_cause"])
async def test_old_alarm_handoff_cannot_consume_new_fault(dosing_hass, boundary):
    h = dosing_hass
    e, n, conn, replies = await accepted_runtime(h)
    h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
    await until(lambda: n.deliveries and n.deliveries[0]["status"] == "handoff_returned")
    if boundary in ("recovered", "recurrence"):
        h.states.async_set("sensor.ph", "5.6", {"unit_of_measurement": "pH"})
        await until(lambda: e.runtime_data.results.alarms["ph_low"][1] is False)
    if boundary == "recurrence":
        h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
        await until(lambda: len(n.deliveries) == 2)
        assert n.deliveries[-1]["code"] == "cooldown"
    if boundary == "policy":
        await policy(conn, replies, e, events=["danger", "failed"])
    why = "emergency_stop" if boundary == "other_cause" else "ph_danger"
    event = await observed_event(e, "failed", why)
    await until(lambda: n.dispatcher.worker.done())
    assert any(
        row["event_id"] == event["event_id"] and row["status"] == "handoff_returned"
        for row in n.deliveries
    )


@pytest.mark.parametrize(
    "kind,why,failure,merged",
    [
        ("stopping", "flow_timeout", "flow_timeout", True),
        ("stopping", "sample_timeout", "sample_timeout", True),
        ("stopping", "flow_timeout", "emergency_stop", False),
        ("stop_unconfirmed", "stop_unconfirmed", "operation_failed", True),
    ],
)
@pytest.mark.parametrize("queued", [False, True])
async def test_fault_escalation_merges_only_a_successful_same_episode(
    dosing_hass, kind, why, failure, merged, queued
):
    e, n, _, _ = await accepted_runtime(dosing_hass)
    first = await observed_event(e, kind, why)
    if not queued:
        await until(lambda: n.deliveries[-1]["status"] == "handoff_returned")
    last = await observed_event(e, "failed", failure)
    # Duplicate event_id never creates another job, including before admission.
    n.enqueue(deepcopy(last))
    await until(lambda: n.dispatcher.worker.done())
    assert any(
        row["event_id"] == first["event_id"] and row["status"] == "handoff_returned"
        for row in n.deliveries
    )
    rows = [row for row in n.deliveries if row["event_id"] == last["event_id"]]
    assert (not rows) if merged else (len(rows) == 1 and rows[0]["status"] == "handoff_returned")
    assert not n.dispatcher.queue
    assert len(n.dispatcher.episodes) <= 64
    assert n.dispatcher.dedupe.count(last["event_id"]) == 1


@pytest.mark.parametrize("attempt", ["expired", "revoked", "queue_full", "evicted"])
async def test_unhanded_alarm_is_not_a_notification_episode(dosing_hass, attempt):
    h = dosing_hass
    e, n, conn, replies = await accepted_runtime(h)
    await policy(conn, replies, e, events=["danger", "failed", "start", "completed"])
    clock = [0.0]
    n.dispatcher.clock = lambda: clock[0]
    blockers = {h.loop.create_future(), h.loop.create_future()}
    n.dispatcher.slots.update(blockers)
    try:
        if attempt == "queue_full":
            for i in range(16):
                clock[0] = float(i * 61)
                await observed_event(e, "completed", "none")
        h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
        await until(lambda: any(row["kind"] == "ph_low" for row in n.deliveries))
        if attempt == "evicted":
            for i in range(15):
                clock[0] += 61
                await observed_event(e, "accepted", "none")
            await observed_event(e, "completed", "none")
        if attempt == "expired":
            clock[0] = 61.0
        if attempt == "revoked":
            await policy(conn, replies, e, events=["danger", "failed", "start", "completed"])
        assert len(n.dispatcher.queue) <= 16
    finally:
        n.dispatcher.slots.difference_update(blockers)
    await until(lambda: n.dispatcher.worker.done())
    alarm = next(row for row in n.deliveries if row["kind"] == "ph_low")
    assert alarm["code"] == (
        "revoked" if attempt == "revoked" else "expired" if attempt == "expired" else "queue_full"
    )
    event = await observed_event(e, "failed", "ph_danger")
    await until(lambda: n.dispatcher.worker.done())
    assert any(
        row["event_id"] == event["event_id"] and row["status"] == "handoff_returned"
        for row in n.deliveries
    )


async def test_provider_failed_alarm_does_not_consume_fault(dosing_hass):
    import logging

    from homeassistant.components.notify import NotifyEntity
    from homeassistant.helpers.entity_component import EntityComponent

    h = dosing_hass
    component = EntityComponent(logging.getLogger(__name__), "notify", h)
    h.data["notify"] = component

    class Sink(NotifyEntity):
        _attr_name = "episode_sink"
        _attr_unique_id = "episode_sink"

        def __init__(self):
            self.calls = 0

        async def async_send_message(self, message, title=None):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("controlled_provider_failure")

    sink = Sink()
    await component.async_add_entities([sink])
    e, n, conn, replies = await accepted_runtime(h)
    await policy(
        conn,
        replies,
        e,
        provider="notify_entity",
        target_entity_id=sink.entity_id,
        events=["danger", "failed"],
    )
    h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
    await until(lambda: n.deliveries and n.deliveries[0]["status"] == "failed")
    assert n.deliveries[0]["code"] == "provider_failed"
    event = await observed_event(e, "failed", "ph_danger")
    await until(lambda: n.dispatcher.worker.done())
    assert sink.calls == 2
    assert any(
        row["event_id"] == event["event_id"] and row["status"] == "handoff_returned"
        for row in n.deliveries
    )


async def test_closing_same_latched_fault_after_source_recovers_still_merges(dosing_hass):
    h = dosing_hass
    e, n, _, _ = await accepted_runtime(h)
    h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
    await until(lambda: n.deliveries and n.deliveries[0]["status"] == "handoff_returned")
    await observed_event(e, "stopping", "ph_danger")
    h.states.async_set("sensor.ph", "5.6", {"unit_of_measurement": "pH"})
    await until(lambda: e.runtime_data.results.alarms["ph_low"][1] is False)
    event = await observed_event(e, "failed", "ph_danger")
    await until(lambda: n.dispatcher.worker.done())
    assert not any(row["event_id"] == event["event_id"] for row in n.deliveries)


async def test_ec_fault_onset_before_alarm_edge_is_correlated(dosing_hass):
    h = dosing_hass
    e, n, _, _ = await accepted_runtime(h)
    # ResultCoordinator publishes lifecycle before its read-only danger observer.
    # Exercise this ordering through its real event seam, not a fake dispatcher.
    await observed_event(e, "stopping", "ec_danger")
    h.states.async_set("sensor.ec", "1.4", {"unit_of_measurement": "mS/cm"})
    await until(lambda: n.deliveries and n.deliveries[0]["status"] == "handoff_returned")
    assert n.deliveries[0]["kind"] == "ec_high"
    event = await observed_event(e, "failed", "ec_danger")
    await until(lambda: n.dispatcher.worker.done())
    assert not any(row["event_id"] == event["event_id"] for row in n.deliveries)
    assert len(n.dispatcher.faults) <= 64
