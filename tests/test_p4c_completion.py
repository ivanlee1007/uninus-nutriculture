"""Non-persistent completion regressions against native Core runtime."""

import asyncio
from copy import deepcopy

import pytest
from homeassistant.core import callback
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5, until
from test_p4c_notifications import connection, ws


async def ready(h):
    e, _ = await prepared(h)
    await save_v5(h, e)
    c, replies = await connection(h)
    return e, e.runtime_data.notifications, c, replies


async def policy(c, replies, e, **changes):
    n = e.runtime_data.notifications
    p = dict(
        enabled=True,
        provider="persistent_notification",
        target_entity_id=None,
        events=["start"],
        cooldown_seconds=60,
    )
    p.update(changes)
    result = await ws(
        c, replies, "save", e, expected_epoch=n.epoch, expected_revision=n.revision, policy=p
    )
    assert result["success"], result


def emit(e):
    from homeassistant.util import dt as dt_util

    e.runtime_data.results.event("accepted", "none", None, dt_util.utcnow().isoformat())


@pytest.mark.parametrize("change", ["revision", "disable", "indeterminate"])
async def test_queued_policy_fence_before_slot(dosing_hass, change):
    from homeassistant.components import persistent_notification as pn

    h = dosing_hass
    e, n, c, replies = await ready(h)
    await policy(c, replies, e)
    received = []

    @callback
    def notice(kind, messages):
        received.extend(messages.values())

    unsub = pn.async_register_callback(h, notice)
    blockers = {h.loop.create_future(), h.loop.create_future()}
    n.dispatcher.slots.update(blockers)
    try:
        emit(e)
        await until(lambda: bool(n.dispatcher.queue))
        await asyncio.sleep(0.06)
        if change == "indeterminate":
            n.indeterminate = True
        else:
            await policy(c, replies, e, enabled=change != "disable")
        n.dispatcher.slots.difference_update(blockers)
        await until(lambda: n.dispatcher.worker.done())
        assert not received, "old policy queued job crossed the native handoff"
        assert n.deliveries[-1]["code"] == "revoked"
    finally:
        n.dispatcher.slots.difference_update(blockers)
        unsub()
        n.close()


@pytest.mark.parametrize("ident", [2**53, True, 1.5])
async def test_private_ws_rejects_unsafe_id_without_effect(dosing_hass, ident):
    from pathlib import Path

    h = dosing_hass
    e, n, c, replies = await ready(h)
    before = n.dto()
    c.async_handle(
        dict(id=ident, type="uninus_nutriculture/notification_v1/get", config_entry_id=e.entry_id)
    )
    await h.async_block_till_done()
    assert not any(m.get("success") for m in replies), "unsafe WS id accepted"
    assert n.dto() == before and not Path(n.store.path).exists()


async def test_native_options_pn_to_notify_rerender_without_save(dosing_hass):
    from pathlib import Path

    from test_p4b_native import owner

    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    await policy(c, replies, e)
    before = Path(n.store.path).read_bytes()
    options = deepcopy(dict(e.options))
    ctx = await owner(h)

    async def open_form():
        f = await h.config_entries.options.async_init(e.entry_id, context={"user_id": ctx.user_id})
        return await h.config_entries.options.async_configure(
            f["flow_id"],
            {
                **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
                "notification_management": True,
            },
        )

    f = await open_form()
    assert "target_entity_id" not in {str(k) for k in f["data_schema"].schema}
    values = dict(
        enabled=True, provider="notify_entity", events=["start"], cooldown_seconds=60, action="save"
    )
    f = await h.config_entries.options.async_configure(f["flow_id"], values)
    assert f["type"] == "form" and not f["errors"], "provider navigation treated as invalid save"
    assert "target_entity_id" in {str(k) for k in f["data_schema"].schema}
    assert Path(n.store.path).read_bytes() == before and dict(e.options) == options
    f = await h.config_entries.options.async_configure(
        f["flow_id"], {**values, "target_entity_id": sink.entity_id}
    )
    assert f["type"] == "abort" and n.policy["provider"] == "notify_entity"
    saved = Path(n.store.path).read_bytes()
    f = await open_form()
    assert "target_entity_id" in {str(k) for k in f["data_schema"].schema}
    f = await h.config_entries.options.async_configure(f["flow_id"], {**values, "action": "cancel"})
    assert f["type"] == "abort"
    assert Path(n.store.path).read_bytes() == saved and dict(e.options) == options
    assert not sink.messages


async def sink_runtime(h):
    import logging

    from homeassistant.components.notify import NotifyEntity
    from homeassistant.helpers.entity_component import EntityComponent

    component = EntityComponent(logging.getLogger(__name__), "notify", h)
    h.data["notify"] = component

    class Sink(NotifyEntity):
        _attr_name = "completion_sink"
        _attr_unique_id = "completion_sink"
        _attr_available = True

        def __init__(self):
            self.messages = []
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def async_send_message(self, message, title=None):
            self.messages.append(message)
            self.entered.set()
            await self.release.wait()

    sink = Sink()
    await component.async_add_entities([sink])
    e, n, c, replies = await ready(h)
    await policy(c, replies, e, provider="notify_entity", target_entity_id=sink.entity_id)
    return e, n, c, replies, sink


async def test_late_policy_ack_never_records_native_timestamp(dosing_hass):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    emit(e)
    await asyncio.wait_for(sink.entered.wait(), 2)
    before = deepcopy(n.deliveries)
    await policy(c, replies, e, enabled=False)
    sink.release.set()
    await until(lambda: n.dispatcher.worker.done())
    assert len(sink.messages) == 1  # admitted effect is not rolled back
    assert h.states.get(sink.entity_id).state == "unknown"
    assert n.deliveries == before


async def test_availability_event_cache_get_pure(dosing_hass, monkeypatch):
    from custom_components.uninus_nutriculture import notification_provider as provider

    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    sink._attr_available = False
    sink.async_write_ha_state()
    await h.async_block_till_done()
    dto = (await ws(c, replies, "get", e))["result"]
    assert dto["availability"] == "unavailable", "cached provider disappearance still available"
    assert dto["error"] == "provider_unavailable"
    assert any(r["entity_id"] == sink.entity_id and not r["available"] for r in dto["catalog"])

    def forbidden(*args):
        raise AssertionError("GET performed provider lookup")

    monkeypatch.setattr(provider, "resolve", forbidden)
    monkeypatch.setattr(provider, "catalog", forbidden)
    assert (await ws(c, replies, "get", e))["result"] == dto


@pytest.mark.parametrize("counter", ["sequence", "observation_revision"])
async def test_result_max_safe_rotates_epoch_retires_old_queue(dosing_hass, counter):
    from custom_components.uninus_nutriculture.results import MAX

    h = dosing_hass
    e, n, c, replies = await ready(h)
    await policy(c, replies, e)
    r = e.runtime_data.results
    blockers = {h.loop.create_future(), h.loop.create_future()}
    n.dispatcher.slots.update(blockers)
    try:
        emit(e)
        old_epoch = r.epoch
        if counter == "sequence":
            r.sequence = MAX
            emit(e)
        else:
            r.cache["observation_revision"] = MAX
            h.states.async_set("sensor.ph", "3.0", {"unit_of_measurement": "pH"})
            await h.async_block_till_done()
        dto = r.dto()
        assert r.epoch != old_epoch, "unsafe result counter failed to rotate epoch"
        assert dto["epoch"] == n.epoch == r.epoch
        assert dto["observation_revision"] <= MAX
        assert dto["latest_event"]["epoch"] == r.epoch
        assert dto["latest_event"]["sequence"] <= MAX
        assert all(j[0]["epoch"] == r.epoch for j in n.dispatcher.queue)
        before = r.dto()
        assert r.dto() == before  # GET does not allocate/rotate
    finally:
        n.dispatcher.slots.difference_update(blockers)
        n.close()
