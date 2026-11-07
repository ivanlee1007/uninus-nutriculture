"""Native authenticated WS and physical Store tracer, no private service calls."""

import asyncio
import json
import logging
from copy import deepcopy
from pathlib import Path

import pytest
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import callback
from homeassistant.helpers.storage import Store
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5, until
from test_p4b_native import owner

DOMAIN = "uninus_nutriculture"
PREFIX = DOMAIN + "/notification_v1/"


async def connection(h):
    ctx = await owner(h)
    user = await h.auth.async_get_user(ctx.user_id)
    replies = []
    conn = ActiveConnection(
        logging.getLogger(__name__),
        h,
        lambda m: replies.append(json.loads(m) if isinstance(m, (str, bytes)) else m),
        user,
        None,
        None,
    )
    return conn, replies


async def ws(conn, replies, op, e, **data):
    ident = conn.last_id + 1
    conn.async_handle(dict(id=ident, type=PREFIX + op, config_entry_id=e.entry_id, **data))
    await until(lambda: any(m.get("id") == ident for m in replies))
    return next(m for m in replies if m.get("id") == ident)


async def test_private_ws_save_physical_store_and_cache(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    conn, replies = await connection(h)
    # Transport-only no-op permits a physical-state assertion before response access.
    if PREFIX + "save" not in h.data["websocket_api"]:

        @callback
        def noop(hass, connection, msg):
            connection.send_result(msg["id"], {})

        import probatio as vol

        websocket_api.async_register_command(
            h,
            PREFIX + "save",
            noop,
            vol.Schema(
                {
                    vol.Required("type"): PREFIX + "save",
                    vol.Required("id"): int,
                    vol.Required("config_entry_id"): str,
                    vol.Required("expected_epoch"): str,
                    vol.Required("expected_revision"): int,
                    vol.Required("policy"): dict,
                }
            ),
        )
    before = deepcopy(dict(e.options))
    epoch = e.runtime_data.results.epoch
    policy = dict(
        enabled=True,
        provider="persistent_notification",
        target_entity_id=None,
        events=["start", "completed"],
        cooldown_seconds=300,
    )
    response = await ws(
        conn, replies, "save", e, expected_epoch=epoch, expected_revision=0, policy=policy
    )
    path = Path(h.config.path(".storage", DOMAIN + ".notification_v1." + e.entry_id))
    assert path.exists(), ("accepted private save has no durable NativeStore document", response)
    assert response["success"], response
    doc = json.loads(path.read_text())
    assert doc["data"]["revision"] == 1
    assert doc["data"]["policy"] == {k: v for k, v in policy.items() if k != "target_entity_id"} | {
        "target_binding": None
    }
    fresh = Store(h, 1, DOMAIN + ".notification_v1." + e.entry_id, private=True, atomic_writes=True)
    assert await fresh.async_load() == doc["data"]
    dto = (await ws(conn, replies, "get", e))["result"]
    assert dto["revision"] == 1 and dto["epoch"] == epoch
    response = await ws(
        conn, replies, "save", e, expected_epoch=epoch, expected_revision=1, policy=policy
    )
    assert response["success"] and json.loads(path.read_text())["data"]["revision"] == 2
    response = await ws(conn, replies, "reconcile", e, expected_epoch=epoch)
    assert response["success"] and response["result"]["revision"] == 2
    assert dict(e.options) == before
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


async def test_native_options_notification_save_reopen_cancel(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    before = deepcopy(dict(e.options))
    f = await h.config_entries.options.async_init(e.entry_id, context={"user_id": ctx.user_id})
    assert "notification_management" in {str(k) for k in f["data_schema"].schema}, (
        "notification native entry absent"
    )
    f = await h.config_entries.options.async_configure(
        f["flow_id"],
        {
            **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            "notification_management": True,
        },
    )
    assert f["step_id"] == "notifications"
    values = dict(
        enabled=True,
        provider="persistent_notification",
        events=["start"],
        cooldown_seconds=60,
        action="save",
    )
    f = await h.config_entries.options.async_configure(f["flow_id"], values)
    assert f["type"] == "abort"
    assert e.runtime_data.notifications.dto()["revision"] == 1
    assert dict(e.options) == before
    f = await h.config_entries.options.async_init(e.entry_id, context={"user_id": ctx.user_id})
    f = await h.config_entries.options.async_configure(
        f["flow_id"],
        {
            **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            "notification_management": True,
        },
    )
    f = await h.config_entries.options.async_configure(f["flow_id"], {**values, "action": "cancel"})
    assert f["type"] == "abort" and e.runtime_data.notifications.dto()["revision"] == 1
    assert dict(e.options) == before


async def test_accepted_event_handoff_pn_not_delivery_confirmed(dosing_hass):
    from homeassistant.components import persistent_notification as pn
    from test_p2_control import toggle
    from test_p3_dosing import start_native

    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    conn, replies = await connection(h)
    policy = dict(
        enabled=True,
        provider="persistent_notification",
        target_entity_id=None,
        events=["start", "completed"],
        cooldown_seconds=300,
    )
    response = await ws(
        conn,
        replies,
        "save",
        e,
        expected_epoch=e.runtime_data.results.epoch,
        expected_revision=0,
        policy=policy,
    )
    assert response["success"], response
    got = []

    @callback
    def notice(kind, messages):
        got.extend(messages.values())

    unsub = pn.async_register_callback(h, notice)
    h.states.async_set("sensor.level", "2.4", {"unit_of_measurement": "m"})
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "refill_enabled")
    await start_native(h, e)
    await until(lambda: not e.runtime_data.control.running)
    await h.async_block_till_done()
    assert got, "accepted opt-in event had no native provider handoff"
    assert any("已受理" in n["message"] for n in got)
    dto = (await ws(conn, replies, "get", e))["result"]
    assert [r["status"] for r in dto["deliveries"]] == ["handoff_returned", "handoff_returned"]
    event_id = dto["deliveries"][0]["event_id"]
    ack = await ws(conn, replies, "ack", e, expected_epoch=dto["epoch"], event_id=event_id)
    assert ack["success"] and ack["result"]["deliveries"][0]["acknowledged"]
    assert not e.runtime_data.control.fault
    unsub()


@pytest.mark.parametrize("feature", [False, True])
async def test_typed_notify_entity_native_identity_title_timestamp_private(dosing_hass, feature):
    from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_component import EntityComponent
    from test_p2_control import toggle
    from test_p3_dosing import start_native

    h = dosing_hass
    component = EntityComponent(logging.getLogger(__name__), "notify", h)
    h.data["notify"] = component

    class Sink(NotifyEntity):
        _attr_name = "private_sink_canary"
        _attr_unique_id = "private_sink_canary"
        _attr_supported_features = NotifyEntityFeature.TITLE if feature else NotifyEntityFeature(0)

        def __init__(self):
            self.messages = []

        async def async_send_message(self, message, title=None):
            self.messages.append((message, title))

    sink = Sink()
    await component.async_add_entities([sink])
    e, _ = await prepared(h)
    await save_v5(h, e)
    conn, replies = await connection(h)
    dto = (await ws(conn, replies, "get", e))["result"]
    assert any(r["entity_id"] == sink.entity_id for r in dto["catalog"]), (
        "loaded native NotifyEntity absent from private catalog"
    )
    public = []

    @callback
    def observe(ev):
        if ev.event_type in ("call_service", DOMAIN + "_result_v1"):
            public.append(str(dict(ev.data)))

    u = h.bus.async_listen("*", observe)
    response = await ws(
        conn,
        replies,
        "save",
        e,
        expected_epoch=dto["epoch"],
        expected_revision=0,
        policy=dict(
            enabled=True,
            provider="notify_entity",
            target_entity_id=sink.entity_id,
            events=["start"],
            cooldown_seconds=60,
        ),
    )
    assert response["success"], response
    binding = response["result"]["policy"]["target_binding"]
    assert binding["registry_entry_id"] == er.async_get(h).async_get(sink.entity_id).id
    h.states.async_set("sensor.level", "2.4", {"unit_of_measurement": "m"})
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "refill_enabled")
    await start_native(h, e)
    await until(lambda: bool(sink.messages))
    await until(lambda: h.states.get(sink.entity_id).state not in ("unknown", "unavailable"))
    assert "已受理" in sink.messages[0][0]
    assert (sink.messages[0][1] is not None) == feature
    assert not any("private_sink_canary" in payload for payload in public)
    assert e.runtime_data.control.fault is None
    u()


@pytest.mark.parametrize(
    "errtext", ["", "provider_timeout secret_canary", "arbitrary secret_canary"]
)
async def test_provider_exception_closed_code_never_control_fault(dosing_hass, errtext):
    from homeassistant.components.notify import NotifyEntity
    from homeassistant.helpers.entity_component import EntityComponent
    from test_p2_control import toggle
    from test_p3_dosing import start_native

    h = dosing_hass
    component = EntityComponent(logging.getLogger(__name__), "notify", h)
    h.data["notify"] = component

    class Sink(NotifyEntity):
        _attr_name = "exception_sink"
        _attr_unique_id = "exception_sink"

        async def async_send_message(self, message, title=None):
            raise RuntimeError(errtext)

    sink = Sink()
    await component.async_add_entities([sink])
    e, _ = await prepared(h)
    await save_v5(h, e)
    conn, replies = await connection(h)
    response = await ws(
        conn,
        replies,
        "save",
        e,
        expected_epoch=e.runtime_data.results.epoch,
        expected_revision=0,
        policy=dict(
            enabled=True,
            provider="notify_entity",
            target_entity_id=sink.entity_id,
            events=["start"],
            cooldown_seconds=60,
        ),
    )
    assert response["success"]
    h.states.async_set("sensor.level", "2.4", {"unit_of_measurement": "m"})
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "refill_enabled")
    await start_native(h, e)
    await until(
        lambda: (
            bool(e.runtime_data.notifications.deliveries)
            and e.runtime_data.notifications.deliveries[-1]["status"] == "failed"
        )
    )
    d = e.runtime_data.notifications.dto()
    assert d["deliveries"][-1]["code"] == "provider_failed"
    assert "secret_canary" not in str(d)
    assert e.runtime_data.control.fault is None


async def test_ws_revoke_private_waiter_before_write(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    conn, replies = await connection(h)
    n = e.runtime_data.notifications
    await n.lock.acquire()
    task = asyncio.create_task(
        ws(
            conn,
            replies,
            "save",
            e,
            expected_epoch=n.epoch,
            expected_revision=0,
            policy=dict(
                enabled=False, provider=None, target_entity_id=None, events=[], cooldown_seconds=300
            ),
        )
    )
    await until(lambda: bool(n.lock._waiters))
    conn.user.is_active = False
    n.lock.release()
    result = await task
    assert not result["success"] and result["error"]["code"] == "unauthorized"
    assert n.revision == 0 and not Path(n.store.path).exists()


async def test_native_writer_cancel_drains_lock_explicit_reconcile(dosing_hass):
    import threading

    from homeassistant.core import Context

    from custom_components.uninus_nutriculture.notification_api import execute

    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    conn, replies = await connection(h)
    n = e.runtime_data.notifications
    gate = threading.Event()
    entered = threading.Event()
    native = n.store._write_prepared_data

    def write(mode, data):
        entered.set()
        assert gate.wait(10)
        return native(mode, data)

    n.store._write_prepared_data = write
    payload = dict(
        config_entry_id=e.entry_id,
        expected_epoch=n.epoch,
        expected_revision=0,
        policy=dict(
            enabled=False, provider=None, target_entity_id=None, events=[], cooldown_seconds=300
        ),
    )
    task = asyncio.create_task(execute(h, Context(user_id=conn.user.id), "save", payload))
    try:
        await until(entered.is_set)
        task.cancel()
        await asyncio.sleep(0.03)
        task.cancel()
        await asyncio.sleep(0.03)
        assert n.lock.locked() and not task.done()
    finally:
        gate.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert n.indeterminate and not n.lock.locked()
    raw = json.loads(Path(n.store.path).read_text())
    assert raw["data"]["revision"] == 1
    result = await ws(conn, replies, "reconcile", e, expected_epoch=n.epoch)
    assert result["success"] and result["result"]["revision"] == 1
    assert not n.indeterminate


async def test_slow_provider_timeout_quarantine_safety_off_and_late_owner_fence(dosing_hass):
    from homeassistant.components.notify import NotifyEntity
    from homeassistant.helpers.entity_component import EntityComponent
    from test_p2_control import toggle
    from test_p3_dosing import start_native
    from test_p3c_flow import plan

    h = dosing_hass
    component = EntityComponent(logging.getLogger(__name__), "notify", h)
    h.data["notify"] = component
    entered = asyncio.Event()
    gate = asyncio.Event()

    class Sink(NotifyEntity):
        _attr_name = "slow_sink"
        _attr_unique_id = "slow_sink"

        async def async_send_message(self, message, title=None):
            entered.set()
            await gate.wait()

    sink = Sink()
    await component.async_add_entities([sink])
    e, _ = await prepared(h)
    p = plan()
    for row in p["rows"]:
        row.update(start_rule="flow_start", delay_seconds=0)
    await save_v5(h, e, p)
    conn, replies = await connection(h)
    n = e.runtime_data.notifications
    result = await ws(
        conn,
        replies,
        "save",
        e,
        expected_epoch=n.epoch,
        expected_revision=0,
        policy=dict(
            enabled=True,
            provider="notify_entity",
            target_entity_id=sink.entity_id,
            events=["start", "stop"],
            cooldown_seconds=60,
        ),
    )
    assert result["success"]
    h.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "nutrient_enabled")
    await start_native(h, e)
    await asyncio.wait_for(entered.wait(), 2)
    pump, circ = h.data["p3_fixture"]["outputs"]
    await asyncio.wait_for(pump.entered_on.wait(), 3)
    await asyncio.wait_for(toggle(h, e, "flow_run", False), 2)
    assert (
        not gate.is_set()
        and not pump.is_on
        and not circ.is_on
        and not e.runtime_data.control.leases
    )
    await until(lambda: n.deliveries[0]["status"] == "timed_out", seconds=7)
    assert len(n.dispatcher.slots) == 1 and not n.dispatcher.native.done()
    assert n.deliveries[0]["code"] == "provider_timeout"
    old = e.runtime_data
    before = deepcopy(n.deliveries)
    e.runtime_data = object()
    try:
        gate.set()
        await until(lambda: n.dispatcher.native.done())
        assert h.states.get(sink.entity_id).state == "unknown"
        assert n.deliveries == before
    finally:
        e.runtime_data = old
        n.close()


async def test_unload_safety_off_before_admitted_native_store_drain(dosing_hass):
    import threading

    from test_p2_control import toggle
    from test_p3_dosing import start_native
    from test_p3c_flow import plan

    h = dosing_hass
    e, _ = await prepared(h)
    p = plan()
    for row in p["rows"]:
        row.update(start_rule="flow_start", delay_seconds=0)
    await save_v5(h, e, p)
    conn, replies = await connection(h)
    n = e.runtime_data.notifications
    h.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "nutrient_enabled")
    await start_native(h, e)
    pump, circ = h.data["p3_fixture"]["outputs"]
    await asyncio.wait_for(pump.entered_on.wait(), 3)
    entered = threading.Event()
    gate = threading.Event()
    native = n.store._write_prepared_data

    def writer(mode, data):
        entered.set()
        assert gate.wait(10)
        return native(mode, data)

    n.store._write_prepared_data = writer
    save = asyncio.create_task(
        ws(
            conn,
            replies,
            "save",
            e,
            expected_epoch=n.epoch,
            expected_revision=0,
            policy=dict(
                enabled=False, provider=None, target_entity_id=None, events=[], cooldown_seconds=300
            ),
        )
    )
    await until(entered.is_set)
    unload = asyncio.create_task(h.config_entries.async_unload(e.entry_id))
    try:
        await asyncio.wait_for(pump.entered_off.wait(), 2)
        await asyncio.sleep(0.1)
        assert not gate.is_set() and not pump.is_on and not circ.is_on
        assert not unload.done(), "unload released runtime before admitted executor write settled"
    finally:
        gate.set()
        await unload
        await save
