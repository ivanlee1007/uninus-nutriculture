"""Owned P4b native safety supplement; frozen product, fake physical I/O only."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import entry
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from test_p2_control import target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import save_v5, until
from test_p4b_native import api
from test_p4b_permit import completed, policy, reports


async def granted(h):
    e, ctx = await completed(h)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    d = await api(h, ctx, e)
    assert d["permit"]["granted"] is True, d
    assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "on"
    return e, ctx


def evidence(h, e, label):
    c, q = e.runtime_data.control, e.runtime_data.quality
    print(
        "MATRIX_EVIDENCE",
        json.dumps(
            dict(
                label=label,
                entry_id=e.entry_id,
                epoch=q.epoch,
                candidate=q.candidate,
                consumed=q.consumed,
                granted=q.granted,
                completion=q.completion,
                running=c.running,
                leases=c.leases,
                late_on=c.late_on,
                owners={
                    s: dict(
                        owns_io=c.flow.stage(s).owns_io,
                        operations={
                            str(k): t.done() for k, t in c.flow.stage(s).operations.items()
                        },
                    )
                    for s in ("refill", "nutrient", "acid", "mix")
                },
                binary_identity=target(h, e, "binary_sensor", "irrigation_permit"),
                binary_states={
                    st.entity_id: st.state
                    for st in h.states.async_all("binary_sensor")
                    if st.attributes.get("config_entry_id") == e.entry_id
                },
                outputs={
                    x.entity_id: dict(physical=x.is_on, native=h.states.get(x.entity_id).state)
                    for x in h.data["p3_fixture"]["outputs"]
                },
                calls=h.data["p3_fixture"]["calls"],
            ),
            default=str,
        ),
    )


async def fresh_without_drain(h):
    for k, v, u in (("ph", 5.6, "pH"), ("ec", 0.87, "mS/cm"), ("level", 2.4, "m")):
        attrs = {**dict(h.states.get("sensor." + k).attributes), "unit_of_measurement": u}
        h.states.async_set("sensor." + k, v, attrs)
        h.states.async_set("sensor." + k, v, attrs)
    await asyncio.sleep(0.04)


async def denied(h, e, ctx):
    d = await api(h, ctx, e)
    assert d["permit"]["granted"] is False, d
    assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "off"
    return d


async def test_held_off_actual_off_no_candidate_release_new_window_grants(dosing_hass):
    h = dosing_hass
    task = asyncio.create_task(completed(h))
    circ = h.data["p3_fixture"]["outputs"][1]
    try:
        await until(
            lambda: any(
                getattr(e, "runtime_data", None) and e.runtime_data.control.acid_stage.owns_io
                for e in h.config_entries.async_entries("uninus_nutriculture")
            ),
            12,
        )
        e = h.config_entries.async_entries("uninus_nutriculture")[0]
        ctx = __import__("homeassistant.core", fromlist=["Context"]).Context(
            user_id=(await h.auth.async_get_users())[0].id
        )
        circ.entered_off.clear()
        circ.off_ack_gate = asyncio.Event()
        await asyncio.wait_for(circ.entered_off.wait(), 5)
        assert not circ.is_on and h.states.get(circ.entity_id).state == "off"
        c = e.runtime_data.control
        assert any(
            not t.done()
            for owner in (c.nutrient_stage, c.acid_stage, c.mix_stage)
            for t in owner.operations.values()
        )
        await fresh_without_drain(h)
        # Explicit quality-domain timing seam keeps real OFF ACK below native timeout.
        q = e.runtime_data.quality
        real_clock = q.clock
        q.clock = lambda: real_clock() + 1.02
        await fresh_without_drain(h)
        q.clock = real_clock
        d = await denied(h, e, ctx)
        evidence(h, e, "held_OFF_ack_physical_OFF")
        assert d["completion"]["state"] != "completed"
        assert e.runtime_data.quality.candidate is None
        circ.off_ack_gate.set()
        e, ctx = await asyncio.wait_for(task, 8)
        await reports(h)
        await asyncio.sleep(1.02)
        await reports(h)
        assert (await api(h, ctx, e))["permit"]["granted"] is True
        evidence(h, e, "released_OFF_new_postclosure_window_grant")
    finally:
        if circ.off_ack_gate:
            circ.off_ack_gate.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 12)


@pytest.mark.parametrize("phase", ["candidate", "granted"])
async def test_native_master_disable_reenable_never_revives(dosing_hass, phase):
    h = dosing_hass
    e, ctx = await (completed(h) if phase == "candidate" else granted(h))
    assert e.runtime_data.quality.candidate is not None
    epoch = e.runtime_data.quality.epoch
    await toggle(h, e, "automation_enabled", False)
    await denied(h, e, ctx)
    assert e.runtime_data.quality.candidate is None
    assert not e.runtime_data.control.master
    evidence(h, e, "master_disabled_" + phase)
    await toggle(h, e, "automation_enabled", True)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    await denied(h, e, ctx)
    assert e.runtime_data.quality.epoch == epoch
    assert not any(x.is_on for x in h.data["p3_fixture"]["outputs"])
    evidence(h, e, "reenable_no_new_run_" + phase)


@pytest.mark.parametrize("result", [False, "pending"])
async def test_real_unload_entry_platform_failure_withdraws_first(dosing_hass, result):
    from custom_components.uninus_nutriculture import async_unload_entry

    h = dosing_hass
    e, ctx = await granted(h)
    q = e.runtime_data.quality
    entered, release = asyncio.Event(), asyncio.Event()

    async def unloader(*args, **kwargs):
        entered.set()
        if result == "pending":
            await release.wait()
        return False

    with patch.object(type(h.config_entries), "async_unload_platforms", unloader):
        task = asyncio.create_task(async_unload_entry(h, e))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            assert q.closed and not q.granted and q.candidate is None
            assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "off"
            evidence(h, e, "unload_platform_" + str(result))
            await fresh_without_drain(h)
            q.expire()
            assert not q.granted and q.candidate is None
            release.set()
            assert await asyncio.wait_for(task, 5) is False
            assert not any(x.is_on for x in h.data["p3_fixture"]["outputs"])
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)


async def test_late_on_after_revoked_epoch_controller_off_not_cutoff(dosing_hass):
    h = dosing_hass
    e, ctx = await granted(h)
    circ = h.data["p3_fixture"]["outputs"][1]
    circ.entered_on.clear()
    circ.entered_off.clear()
    circ.on_apply_gate = asyncio.Event()
    original = circ.async_turn_on

    # Fake provider deliberately survives caller cancellation; no controller mock.
    async def resistant(**kwargs):
        task = asyncio.create_task(original(**kwargs))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await task

    circ.async_turn_on = resistant
    cutoff = h.loop.call_later(7, circ.local_cutoff)
    stop = None
    transitions = []
    late_physical_on = asyncio.Event()
    from homeassistant.core import callback

    @callback
    def observed(event):
        if event.data.get("entity_id") == circ.entity_id:
            new = event.data.get("new_state")
            transitions.append(new.state if new else None)
            if new and new.state == "on":
                late_physical_on.set()

    unsub = h.bus.async_listen("state_changed", observed)
    off_baseline = h.data["p3_fixture"]["calls"].count(("circulation", "off"))
    try:
        e.runtime_data.control.run_stage = "mix"
        await e.runtime_data.control.mix_stage.start(ctx, None)
        await asyncio.wait_for(circ.entered_on.wait(), 3)
        await denied(h, e, ctx)
        stop = asyncio.create_task(toggle(h, e, "automation_enabled", False))
        await asyncio.wait_for(circ.entered_off.wait(), 3)
        assert not circ.is_on
        circ.entered_off.clear()
        circ.on_apply_gate.set()
        await asyncio.wait_for(late_physical_on.wait(), 3)
        await until(
            lambda: h.data["p3_fixture"]["calls"].count(("circulation", "off")) >= off_baseline + 2,
            5,
        )
        await until(lambda: not circ.is_on, 3)
        await asyncio.wait_for(stop, 8)
        assert h.states.get(circ.entity_id).state == "off"
        assert ("circulation", "device_local_cutoff") not in h.data["p3_fixture"]["calls"]
        await fresh_without_drain(h)
        await denied(h, e, ctx)
        assert e.runtime_data.quality.candidate is None
        print("LATE_ON_NATIVE_TRANSITIONS", transitions)
        assert "on" in transitions and transitions[-1] == "off"
        evidence(h, e, "latephysicalON_controller_reclosed")
    finally:
        circ.on_apply_gate.set()
        cutoff.cancel()
        unsub()
        if stop:
            await asyncio.wait_for(asyncio.gather(stop, return_exceptions=True), 10)


async def test_actual_shared_circulation_lease_no_early_candidate(dosing_hass):
    h = dosing_hass
    from test_p3c_flow import plan

    p = plan()
    next(r for r in p["rows"] if r["stage"] == "nutrient")["start_rule"] = "after_previous_started"

    async def shared_plan(hass, e):
        return await save_v5(hass, e, flow_plan=p)

    with patch("test_p4b_permit.save_v5", shared_plan):
        task = asyncio.create_task(completed(h))
        # Native setup/save executes before leaving the temporary helper seam.
        await until(
            lambda: any(
                getattr(e, "runtime_data", None) and e.runtime_data.control.flow.active
                for e in h.config_entries.async_entries("uninus_nutriculture")
            ),
            8,
        )
    try:
        circ = h.data["p3_fixture"]["outputs"][1]
        await asyncio.wait_for(circ.entered_on.wait(), 5)
        # The stock helper keeps refill open through mix; close it through a real
        # level event so chemical admission can legally overlap the mixing lease.
        h.states.async_set("sensor.level", "2.4", {"unit_of_measurement": "m"})
        await until(
            lambda: any(
                getattr(e, "runtime_data", None) and len(e.runtime_data.control.leases) >= 2
                for e in h.config_entries.async_entries("uninus_nutriculture")
            ),
            10,
        )
        e = h.config_entries.async_entries("uninus_nutriculture")[0]
        c = e.runtime_data.control
        assert len(c.leases) >= 2
        assert len({json.dumps(v[0], sort_keys=True) for v in c.leases.values()}) == 1
        assert len({v[3] for v in c.leases.values()}) >= 2
        assert not e.runtime_data.quality.granted
        assert e.runtime_data.quality.candidate is None
        assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "off"
        evidence(h, e, "actual_shared_circulation_owners")
        e, ctx = await asyncio.wait_for(task, 15)
        assert not c.leases
        await reports(h)
        await asyncio.sleep(1.02)
        await reports(h)
        assert (await api(h, ctx, e))["permit"]["granted"] is True
        evidence(h, e, "sharedlease_release_fullflow_grant")
    finally:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 20)


async def test_two_real_same_name_entries_policy_epoch_candidate_isolation(dosing_hass):
    h = dosing_hass
    a, ctx = await granted(h)
    b = entry(options={"control_contract_version": 4, "control": {"commissioned": False}})
    await h.config_entries.async_add(b)
    await h.async_block_till_done()
    await save_v5(h, b)
    assert a.entry_id != b.entry_id and a.title == b.title
    da, db = await api(h, ctx, a), await api(h, ctx, b)
    assert da["epoch"] != db["epoch"]
    assert db["permit"]["granted"] is False and db["completion"]["state"] == "none"
    assert b.runtime_data.quality.candidate is None
    before_a = deepcopy(dict(a.options))
    qa = a.runtime_data.quality
    fence_a = (qa.epoch, qa.candidate, qa.consumed, qa.hard)
    await policy(h, b, ctx, stable_samples=3)
    assert dict(a.options) == before_a
    assert (qa.epoch, qa.candidate, qa.consumed, qa.hard) == fence_a
    assert (await api(h, ctx, b))["policy"]["stable_samples"] == 3
    assert (await api(h, ctx, a))["policy"]["stable_samples"] == 2
    assert (await api(h, ctx, a))["permit"]["granted"] is True
    await denied(h, b, ctx)
    evidence(h, a, "slot_A_preserved")
    evidence(h, b, "slot_B_no_A_receipt")


async def test_wrong_target_cas_rejected_without_any_commit(dosing_hass):
    h = dosing_hass
    a, ctx = await granted(h)
    b = entry(options={"control_contract_version": 4, "control": {"commissioned": False}})
    await h.config_entries.async_add(b)
    await h.async_block_till_done()
    await save_v5(h, b)
    da = await api(h, ctx, a)
    before = {e.entry_id: deepcopy(dict(e.options)) for e in (a, b)}
    storage = Path(h.config.path(".storage/core.config_entries"))
    await h.async_block_till_done()
    store = h.config_entries._store
    # Flush the REAL native Store before rejection, so disk equality is non-vacuous.
    await store.async_save(h.config_entries._data_to_save())
    assert storage.is_file()
    disk = storage.read_bytes()
    scheduled = []
    original_delay_save = type(store).async_delay_save

    def traced_delay_save(instance, *args, **kwargs):
        if instance is store:
            scheduled.append(True)
        return original_delay_save(instance, *args, **kwargs)

    p = deepcopy(da["policy"])
    with patch.object(type(store), "async_delay_save", traced_delay_save):
        with pytest.raises(ServiceValidationError, match="conflict"):
            await api(
                h,
                ctx,
                b,
                "save_quality_policy_v1",
                policy=p,
                expected_policy_revision=da["policy_revision"],
                expected_settings_revision=da["settings_revision"],
                expected_flow_plan_revision=da["flow_plan_revision"],
            )
    assert not scheduled
    print("REAL_STORE_REJECT_ZERO_COMMIT", len(disk), len(scheduled))
    assert {e.entry_id: dict(e.options) for e in (a, b)} == before
    assert (storage.read_bytes() if storage.exists() else None) == disk
    assert (await api(h, ctx, a))["permit"]["granted"] is True
    await denied(h, b, ctx)
    evidence(h, a, "wrong_target_CAS_zero_commit")


@pytest.mark.parametrize("key", ["irrigation_permit", "quality_status"])
async def test_owned_native_unique_identity_replacement_revokes(dosing_hass, key):
    h = dosing_hass
    e, ctx = await granted(h)
    domain = "binary_sensor" if key == "irrigation_permit" else "sensor"
    identity = target(h, e, domain, key)
    q = e.runtime_data.quality
    old_epoch = q.epoch
    er.async_get(h).async_update_entity(identity, new_unique_id="replacement-" + key)
    await asyncio.sleep(0.04)
    assert q.epoch != old_epoch and not q.granted and q.candidate is None
    await fresh_without_drain(h)
    assert (await api(h, ctx, e))["permit"]["granted"] is False
    assert h.states.get(identity).state != "on"
    evidence(h, e, "owned_native_identity_replaced_" + key)
