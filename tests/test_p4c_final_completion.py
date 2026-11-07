"""Final non-persistent native regressions; protected Store remains unchanged."""

import asyncio
from copy import deepcopy

import pytest
from homeassistant.core import callback
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import plan, prepared, save_v5, until
from test_p4c_completion import emit, policy, ready, sink_runtime
from test_p4c_results import read


@pytest.mark.parametrize("counter", ["observation_revision", "sequence"])
@pytest.mark.parametrize("boundary", ["active", "terminal"])
async def test_native_nested_epoch_overflow(dosing_hass, counter, boundary):
    from custom_components.uninus_nutriculture.results import MAX

    h = dosing_hass
    e, _ = await prepared(h)
    p = plan()
    for row in p["rows"]:
        row.update(start_rule="flow_start", delay_seconds=0)
    await save_v5(h, e, p)
    n = e.runtime_data.notifications
    from test_p4c_notifications import connection

    conn, replies = await connection(h)
    await policy(conn, replies, e, events=["start", "stop", "danger"])
    r = e.runtime_data.results
    qepoch = e.runtime_data.quality.epoch
    events = []

    @callback
    def observed(ev):
        events.append(deepcopy(dict(ev.data)))

    unsub = h.bus.async_listen("uninus_nutriculture_result_v1", observed)
    blockers = {h.loop.create_future(), h.loop.create_future()}
    n.dispatcher.slots.update(blockers)
    pump, circ = h.data["p3_fixture"]["outputs"]
    try:
        h.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
        await toggle(h, e, "automation_enabled")
        await toggle(h, e, "nutrient_enabled")
        await start_native(h, e)
        await asyncio.wait_for(pump.entered_on.wait(), 3)
        await until(lambda: r.dto()["current_run"] is not None)
        old = r.epoch
        observations = []
        native_observe = r.observe

        def observe_boundary():
            native_observe()
            observations.append((deepcopy(r.run), r.dto()))

        r.observe = observe_boundary  # owned observer spy; execute original unmodified
        accepted = deepcopy(r.dto()["current_run"])
        if counter == "sequence":
            r.sequence = MAX
        else:
            r.cache["observation_revision"] = MAX
        if boundary == "terminal":
            await toggle(h, e, "flow_run", False)
            await until(lambda: r.dto()["last_result"] is not None)
        else:
            # Hold real OFF acknowledgement: stopping remains an active run.
            pump.off_ack_gate = asyncio.Event()
            stop = asyncio.create_task(toggle(h, e, "automation_enabled", False))
            await asyncio.wait_for(pump.entered_off.wait(), 2)
            await until(lambda: r.epoch != old)
        assert observations
        for observed_run, snapshot in observations:
            assert all(
                row is None or row["epoch"] == snapshot["epoch"]
                for row in (observed_run, snapshot["current_run"], snapshot["last_result"])
            ), "observer returned stale nested epoch"
        dto = await read(h, e)
        assert dto["epoch"] != old
        assert dto["epoch"] == r.epoch == n.epoch
        nested = [r.run, dto["current_run"], dto["last_result"]]
        assert all(row is None or row["epoch"] == dto["epoch"] for row in nested), (
            "nested run restored stale pre-rotation epoch"
        )
        assert dto["latest_event"]["epoch"] == dto["epoch"]
        assert dto["latest_event"]["run"]["epoch"] == dto["epoch"]
        assert dto["observation_revision"] <= MAX and dto["latest_event"]["sequence"] <= MAX
        assert all(job[0]["epoch"] == r.epoch for job in n.dispatcher.queue)
        row = dto["current_run"] or dto["last_result"]
        assert row["run_id"] == accepted["run_id"] and row["accepted_at"] == accepted["accepted_at"]
        assert sum(ev["kind"] == "accepted" for ev in events) == 1
        assert e.runtime_data.quality.epoch == qepoch
        for _ in range(3):
            assert await read(h, e) == dto
        if boundary == "terminal":
            assert not pump.is_on and not circ.is_on and not e.runtime_data.control.leases
    finally:
        if pump.off_ack_gate is not None:
            pump.off_ack_gate.set()
        if "stop" in locals():
            await stop
        n.dispatcher.slots.difference_update(blockers)
        unsub()
        n.close()
        await toggle(h, e, "flow_run", False)


async def test_queued_native_target_change_a_to_b(dosing_hass):
    h = dosing_hass
    e, n, conn, replies, a = await sink_runtime(h)
    b = type(a)()
    b._attr_unique_id = "completion_b"
    b._attr_name = "completion_b"
    await h.data["notify"].async_add_entities([b])
    a.release.set()
    b.release.set()
    blockers = {h.loop.create_future(), h.loop.create_future()}
    n.dispatcher.slots.update(blockers)
    try:
        emit(e)
        await until(lambda: bool(n.dispatcher.queue))
        await asyncio.sleep(0.06)
        await policy(conn, replies, e, provider="notify_entity", target_entity_id=b.entity_id)
        n.dispatcher.slots.difference_update(blockers)
        await until(lambda: n.dispatcher.worker.done())
        assert not a.messages and not b.messages
        assert n.deliveries[-1]["code"] == "revoked"
        assert h.states.get(a.entity_id).state == h.states.get(b.entity_id).state == "unknown"
    finally:
        n.dispatcher.slots.difference_update(blockers)
        n.close()


async def test_native_registry_identity_cache_and_recreation(dosing_hass):
    from homeassistant.exceptions import ServiceValidationError
    from homeassistant.helpers import entity_registry as er
    from test_p4c_notifications import ws

    from custom_components.uninus_nutriculture.notification_provider import resolve

    h = dosing_hass
    e, n, conn, replies, sink = await sink_runtime(h)
    reg = er.async_get(h)
    saved = deepcopy(n.policy["target_binding"])
    old = sink.entity_id
    reg.async_update_entity(old, new_entity_id="notify.renamed_completion")
    await h.async_block_till_done()
    assert resolve(h, saved) is sink
    dto = (await ws(conn, replies, "get", e))["result"]
    assert dto["availability"] == "available"
    assert any(row["entity_id"] == sink.entity_id for row in dto["catalog"])
    sink._attr_available = False
    sink.async_write_ha_state()
    await h.async_block_till_done()
    assert (await ws(conn, replies, "get", e))["result"]["availability"] == "unavailable"
    sink._attr_available = True
    sink.async_write_ha_state()
    await h.async_block_till_done()
    entity_id = sink.entity_id
    await h.data["notify"].async_remove_entity(entity_id)
    reg.async_remove(entity_id)
    await h.async_block_till_done()
    assert (await ws(conn, replies, "get", e))["result"]["availability"] == "unavailable"
    replacement = type(sink)()
    replacement._attr_unique_id = "replacement_identity"
    replacement._attr_name = "renamed_completion"
    replacement.entity_id = entity_id
    await h.data["notify"].async_add_entities([replacement])
    await h.async_block_till_done()
    assert replacement.entity_id == entity_id
    assert reg.async_get(entity_id).id != saved["registry_entry_id"]
    with pytest.raises(ServiceValidationError, match="provider_unavailable"):
        resolve(h, saved)
    assert (await ws(conn, replies, "get", e))["result"]["availability"] == "unavailable"
    assert not replacement.messages


async def test_saved_target_outside_catalog_limit_and_fresh_setup(dosing_hass):
    from pathlib import Path

    from homeassistant.helpers import entity_registry as er
    from test_p4c_notifications import ws

    h = dosing_hass
    e, n, conn, replies, sink = await sink_runtime(h)
    er.async_get(h).async_update_entity(sink.entity_id, new_entity_id="notify.zzzz_saved")
    entities = []
    for index in range(257):
        item = type(sink)()
        item._attr_unique_id = f"catalog_{index:03}"
        item._attr_name = f"aaa_catalog_{index:03}"
        entities.append(item)
    await h.data["notify"].async_add_entities(entities)
    await h.async_block_till_done()
    dto = (await ws(conn, replies, "get", e))["result"]
    assert len(dto["catalog"]) == 256
    assert any(row["entity_id"] == sink.entity_id and row["available"] for row in dto["catalog"])
    before = Path(n.store.path).read_bytes()
    old_epoch = n.epoch
    assert await h.config_entries.async_reload(e.entry_id)
    fresh = e.runtime_data.notifications
    dto = (await ws(conn, replies, "get", e))["result"]
    assert fresh is not n and fresh.epoch != old_epoch
    assert Path(fresh.store.path).read_bytes() == before
    assert dto["availability"] == "available", "fresh setup cached pre-load default provider"
    assert len(dto["catalog"]) == 256
    assert any(row["entity_id"] == sink.entity_id and row["available"] for row in dto["catalog"])
    assert not sink.messages


async def test_master_flow_off_danger_episode_invalid_and_native_stop(dosing_hass):
    from homeassistant.components import persistent_notification as pn

    h = dosing_hass
    e, n, conn, replies = await ready(h)
    await policy(conn, replies, e, events=["danger"])
    got = []

    @callback
    def notice(kind, messages):
        got.extend(messages.values())

    unsub = pn.async_register_callback(h, notice)
    control = e.runtime_data.control
    try:
        await toggle(h, e, "flow_run", False)
        await toggle(h, e, "automation_enabled", False)
        assert not control.master and not control.flow.active
        h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
        await until(lambda: bool(got))
        await until(lambda: n.dispatcher.worker.done())
        assert len(got) == 1
        snapshot = e.runtime_data.results.dto()
        for _ in range(4):
            e.runtime_data.publish()
        h.states.async_set("sensor.ph", "nan", {"unit_of_measurement": "pH"})
        h.states.async_set("sensor.ec", "unknown", {"unit_of_measurement": "mS/cm"})
        await h.async_block_till_done()
        assert len(got) == 1 and e.runtime_data.results.dto() == snapshot
        assert control.fault is None
        assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
        # Actual native lifecycle, not a manually assigned CoreState.
        # SDK force executes real stop stages from this fixture's not_running state.
        await h.async_stop(force=True)
        assert n.closed and e.runtime_data.results.closed and not n.live()
        h.states.async_set("sensor.ec", "1.4", {"unit_of_measurement": "mS/cm"})
        await asyncio.sleep(0.06)
        assert len(got) == 1 and not n.dispatcher.queue
    finally:
        unsub()
