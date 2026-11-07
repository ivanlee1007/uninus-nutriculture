"""Native reload retains entry quota until the real provider settles."""

import asyncio

import pytest
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import until
from test_p4c_completion import policy, sink_runtime


async def test_same_entry_retired_native_keeps_entry_one(dosing_hass):
    h = dosing_hass
    e, old, c, replies, sink = await sink_runtime(h)
    await policy(
        c, replies, e, provider="notify_entity", target_entity_id=sink.entity_id, events=["danger"]
    )
    old_epoch = old.epoch
    try:
        h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
        await until(lambda: len(sink.messages) == 1)
        assert old.policy["enabled"] and old.policy["provider"] == "notify_entity"
        assert not sink.release.is_set() and not old.dispatcher.native.done()
        h.states.async_set("sensor.ph", "5.6", {"unit_of_measurement": "pH"})
        await asyncio.sleep(0.05)
        assert await h.config_entries.async_reload(e.entry_id)
        fresh = e.runtime_data.notifications
        assert fresh is not old and fresh.epoch != old_epoch and old.closed
        assert fresh.dispatcher.slots is old.dispatcher.slots
        h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
        await until(lambda: bool(fresh.deliveries))
        await asyncio.sleep(0.2)
        pending = [t for t in fresh.dispatcher.slots if not t.done()]
        print(
            {
                "old_closed": old.closed,
                "new_epoch": fresh.epoch != old_epoch,
                "old_pending": not old.dispatcher.native.done(),
                "pending": len(pending),
                "provider_calls": len(sink.messages),
                "release": sink.release.is_set(),
            }
        )
        assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
        assert len(pending) == 1, "same entry owns two unsettled native slots across reload"
        assert len(sink.messages) == 1, "second provider crossed the same-entry quota"
        assert fresh.dispatcher.queue and fresh.dispatcher.native is None
    finally:
        sink.release.set()
        e.runtime_data.notifications.close()
        await until(lambda: not old.dispatcher.slots)


async def reloaded_queue(h, other=False):
    """Admit actual A provider, reload natively, then queue a fresh alarm."""
    e, old, c, replies, sink = await sink_runtime(h)
    await policy(
        c, replies, e, provider="notify_entity", target_entity_id=sink.entity_id, events=["danger"]
    )
    b_entry = b_sink = None
    try:
        if other:
            from conftest import entry

            b_sink = type(sink)()
            b_sink._attr_unique_id = "reload_quota_b"
            b_sink._attr_name = "reload_quota_b"
            await h.data["notify"].async_add_entities([b_sink])
            b_entry = entry("Quota B", options=dict(e.options))
            await h.config_entries.async_add(b_entry)
            await h.async_block_till_done()  # no provider has been admitted yet
            await policy(
                c, replies, b_entry, provider="notify_entity", target_entity_id=b_sink.entity_id
            )
        h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
        await until(lambda: len(sink.messages) == 1)
        assert not old.dispatcher.native.done() and not sink.release.is_set()
        h.states.async_set("sensor.ph", "5.6", {"unit_of_measurement": "pH"})
        await asyncio.sleep(0.05)
        assert await h.config_entries.async_reload(e.entry_id)
        fresh = e.runtime_data.notifications
        assert old.closed and fresh.epoch != old.epoch
        h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
        await until(lambda: bool(fresh.dispatcher.queue))
        await asyncio.sleep(0.06)
        assert len(sink.messages) == len(old.dispatcher.slots) == 1
        return e, old, fresh, c, replies, sink, b_entry, b_sink
    except BaseException:
        sink.release.set()
        if b_sink is not None:
            b_sink.release.set()
        e.runtime_data.notifications.close()
        if b_entry is not None:
            b_entry.runtime_data.notifications.close()
        await until(lambda: not old.dispatcher.slots)
        raise


async def test_settlement_handoff_and_old_callback_identity(dosing_hass):
    h = dosing_hass
    e = sink = None
    try:
        e, old, fresh, _, _, sink, _, _ = await reloaded_queue(h)
        old_task = old.dispatcher.native
        settled = next(cb for cb, _ in old_task._callbacks if cb.__name__ == "settled")
        gate = sink.release
        sink.release = asyncio.Event()  # next real invocation has its own hold
        gate.set()
        await until(lambda: len(sink.messages) == 2)
        new_task = fresh.dispatcher.native
        assert old_task.done() and not new_task.done()
        assert old.dispatcher.entry_slots[e.entry_id] is new_task
        settled(old_task)
        settled(old_task)  # late/duplicate old callback cannot release the new owner
        assert fresh.dispatcher.entry_slots[e.entry_id] is new_task
        assert fresh.dispatcher.slots == {new_task}
        print(
            {
                "settled_old": old_task.done(),
                "provider_calls": len(sink.messages),
                "new_pending": not new_task.done(),
                "late_callback_preserved": True,
            }
        )
    finally:
        if sink is not None:
            sink.release.set()
        if e is not None:
            e.runtime_data.notifications.close()
            await until(lambda: not old.dispatcher.slots)
            assert not old.dispatcher.entry_slots


@pytest.mark.parametrize("change", ["disable", "epoch", "ttl", "reload"])
async def test_reload_blocked_queue_revocation_expiry_and_repeat(dosing_hass, change):
    h = dosing_hass
    e = sink = None
    try:
        e, old, fresh, c, replies, sink, _, _ = await reloaded_queue(h)
        if change == "disable":
            await policy(
                c,
                replies,
                e,
                enabled=False,
                provider="notify_entity",
                target_entity_id=sink.entity_id,
                events=["danger"],
            )
        elif change == "epoch":
            queued_epoch = fresh.epoch
            e.runtime_data.results.rotate_epoch()
        elif change == "ttl":
            now = fresh.dispatcher.clock()
            fresh.dispatcher.clock = lambda: now + 61
        else:
            # Third runtime still cannot forget the first runtime's actual effect.
            h.states.async_set("sensor.ph", "5.6", {"unit_of_measurement": "pH"})
            await asyncio.sleep(0.05)
            assert await h.config_entries.async_reload(e.entry_id)
            third = e.runtime_data.notifications
            assert fresh.closed and third.epoch != fresh.epoch
            h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
            await until(lambda: bool(third.dispatcher.queue))
            await asyncio.sleep(0.12)
            assert len(old.dispatcher.slots) == len(sink.messages) == 1
            assert third.dispatcher.native is None
            fresh = third
        if change != "reload":
            await until(lambda: fresh.dispatcher.worker.done())
            assert not fresh.dispatcher.queue
            if change == "epoch":
                assert fresh.epoch != queued_epoch and not fresh.deliveries
            else:
                assert fresh.deliveries[-1]["code"] == ("expired" if change == "ttl" else "revoked")
        assert not old.dispatcher.native.done() and not sink.release.is_set()
        assert len(fresh.dispatcher.entry_slots) == len(sink.messages) == 1
        sink.release.set()
        await until(lambda: not old.dispatcher.slots)
        await until(lambda: fresh.dispatcher.worker.done())
        assert len(sink.messages) == (2 if change == "reload" else 1)
        assert not fresh.dispatcher.entry_slots
        assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
    finally:
        if sink is not None:
            sink.release.set()
        if e is not None:
            e.runtime_data.notifications.close()
            await until(lambda: not old.dispatcher.slots)


async def test_other_entry_can_use_second_global_slot(dosing_hass):
    from test_p4c_completion import emit

    h = dosing_hass
    e = sink = b_sink = None
    try:
        e, old, fresh, _, _, sink, b, b_sink = await reloaded_queue(h, other=True)
        emit(b)
        await until(lambda: len(b_sink.messages) == 1)
        assert len(sink.messages) == 1 and fresh.dispatcher.native is None
        assert len(fresh.dispatcher.slots) == 2
        assert set(fresh.dispatcher.entry_slots) == {e.entry_id, b.entry_id}
        assert (
            not old.dispatcher.native.done()
            and not b.runtime_data.notifications.dispatcher.native.done()
        )
        assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
        print(
            {
                "A_provider_calls": len(sink.messages),
                "B_provider_calls": len(b_sink.messages),
                "global_pending": len(fresh.dispatcher.slots),
                "entry_owners": len(fresh.dispatcher.entry_slots),
            }
        )
    finally:
        if sink is not None:
            sink.release.set()
        if b_sink is not None:
            b_sink.release.set()
        if e is not None:
            e.runtime_data.notifications.close()
            b.runtime_data.notifications.close()
            await until(lambda: not old.dispatcher.slots)
            assert not old.dispatcher.entry_slots
