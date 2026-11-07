"""Fresh authorized persistence redo: registered native WS, real native storage."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5, until
from test_p4c_notifications import PREFIX, connection, ws

POLICY = dict(
    enabled=True,
    provider="persistent_notification",
    target_entity_id=None,
    events=["start", "completed"],
    cooldown_seconds=300,
)


async def ready(h):
    e, _ = await prepared(h)
    await save_v5(h, e)
    conn, replies = await connection(h)
    return e, e.runtime_data.notifications, conn, replies


async def save(conn, replies, e, n, policy=None):
    return await ws(
        conn,
        replies,
        "save",
        e,
        expected_epoch=n.epoch,
        expected_revision=n.revision,
        policy=deepcopy(POLICY if policy is None else policy),
    )


async def test_registered_save_creates_native_durable_candidate(dosing_hass):
    h = dosing_hass
    e, n, conn, replies = await ready(h)
    assert PREFIX + "save" in h.data["websocket_api"]
    initial = await ws(conn, replies, "get", e)
    assert initial["success"] and initial["result"]["revision"] == 0
    assert not Path(n.store.path).exists()
    before = deepcopy(dict(e.options))
    response = await save(conn, replies, e, n)
    assert response["success"], response  # Prove routing and native authorization first.
    assert Path(n.store.path).exists(), (
        "successful registered Save lacks physical NativeStore candidate"
    )
    envelope = json.loads(Path(n.store.path).read_text())
    assert envelope["version"] == 1 and envelope["key"] == n.store.key
    assert envelope["data"] == dict(
        schema_version=1,
        config_entry_id=e.entry_id,
        revision=1,
        policy={k: v for k, v in POLICY.items() if k != "target_entity_id"}
        | {"target_binding": None},
    )
    assert response["result"]["revision"] == 1
    assert dict(e.options) == before
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


async def test_swallowed_native_failure_cannot_confirm_identical_disk(dosing_hass, caplog):
    from homeassistant.helpers.storage import Store
    from homeassistant.util.file import WriteError

    h = dosing_hass
    e, n, conn, replies = await ready(h)
    candidate = dict(
        schema_version=1,
        config_entry_id=e.entry_id,
        revision=1,
        policy={k: v for k, v in POLICY.items() if k != "target_entity_id"}
        | {"target_binding": None},
    )
    # Equal old disk must not disguise the SDK's swallowed native write failure.
    await Store(h, 1, n.store.key, private=True, atomic_writes=True).async_save(candidate)

    def fail(mode, data):
        raise WriteError("private_store_canary")

    n.store._write_prepared_data = fail
    response = await save(conn, replies, e, n)
    assert not response["success"], "equal readback falsely confirms swallowed native failure"
    assert response["error"]["code"] in ("storage_failed", "indeterminate")
    assert n.indeterminate and n.revision == 0
    assert "private_store_canary" not in str(response) + str(n.dto())
    assert any(
        r.name == "homeassistant.helpers.storage" and "Error writing config" in r.message
        for r in caplog.records
    ), "native SDK diagnostic must remain intact"


@pytest.mark.parametrize(
    "malformation",
    [
        "duplicate",
        "schema_bool",
        "revision_bool",
        "revision_float",
        "revision_overflow",
        "extra",
        "foreign",
        "unicode",
        "nonfinite",
    ],
)
async def test_reconcile_rejects_corrupt_physical_envelope(dosing_hass, malformation):
    e, n, conn, replies = await ready(dosing_hass)
    assert (await save(conn, replies, e, n))["success"]
    original = Path(n.store.path).read_bytes()
    raw = json.loads(original)
    if malformation == "duplicate":
        bad = original.decode().replace('"revision": 1', '"revision": 0, "revision": 1')
        assert bad != original.decode(), "fixture did not insert duplicate key"
    else:
        if malformation == "schema_bool":
            raw["data"]["schema_version"] = True
        if malformation == "revision_bool":
            raw["data"]["revision"] = True
        if malformation == "revision_float":
            raw["data"]["revision"] = 1.0
        if malformation == "revision_overflow":
            raw["data"]["revision"] = 2**53
        if malformation == "extra":
            raw["data"]["policy"]["secret_canary"] = "secret_canary"
        if malformation == "foreign":
            raw["data"]["config_entry_id"] = "other"
        if malformation == "unicode":
            raw["data"]["policy"]["events"] = ["start\u202e"]
        if malformation == "nonfinite":
            raw["data"]["policy"]["cooldown_seconds"] = float("nan")
        bad = json.dumps(raw)
    Path(n.store.path).write_text(bad)
    before = deepcopy(n.policy)
    response = await ws(conn, replies, "reconcile", e, expected_epoch=n.epoch)
    assert not response["success"], (malformation, "corrupt disk accepted")
    assert n.indeterminate and n.policy == before and n.revision == 1
    assert "secret_canary" not in str(response) + str(n.dto())
    assert Path(n.store.path).read_text() == bad


async def test_saved_readback_failure_requires_explicit_reconcile(dosing_hass):
    e, n, conn, replies = await ready(dosing_hass)
    physical = n.physical

    def fail():
        raise OSError("private_readback_canary")

    n.physical = fail
    try:
        response = await save(conn, replies, e, n)
    finally:
        n.physical = physical
    assert not response["success"] and n.indeterminate and n.revision == 0
    assert json.loads(Path(n.store.path).read_text())["data"]["revision"] == 1
    assert "private_readback_canary" not in str(response) + str(n.dto())
    dto = (await ws(conn, replies, "get", e))["result"]
    assert dto["availability"] == "indeterminate" and dto["revision"] == 0
    response = await ws(conn, replies, "reconcile", e, expected_epoch=n.epoch)
    assert response["success"] and response["result"]["revision"] == 1
    assert not n.indeterminate


async def test_regressing_revision_remains_quarantined(dosing_hass):
    e, n, conn, replies = await ready(dosing_hass)
    assert (await save(conn, replies, e, n))["success"]
    old = Path(n.store.path).read_bytes()
    assert (await save(conn, replies, e, n))["success"]
    Path(n.store.path).write_bytes(old)
    response = await ws(conn, replies, "reconcile", e, expected_epoch=n.epoch)
    assert not response["success"] and n.indeterminate and n.revision == 2


async def test_setup_reloads_private_policy_without_replay(dosing_hass):
    h = dosing_hass
    e, n, conn, replies = await ready(h)
    assert (await save(conn, replies, e, n))["success"]
    original = Path(n.store.path).read_bytes()
    old_epoch = n.epoch
    assert await h.config_entries.async_reload(e.entry_id)
    n = e.runtime_data.notifications
    assert n.epoch != old_epoch and n.revision == 1 and n.policy["enabled"]
    assert n.dto()["availability"] == "available"
    assert not n.deliveries and e.runtime_data.results.dto()["last_result"] is None
    assert Path(n.store.path).read_bytes() == original


async def test_cache_get_cas_invalid_and_ack_do_not_write(dosing_hass):
    e, n, conn, replies = await ready(dosing_hass)

    def forbidden():
        raise AssertionError("GET must not touch physical storage")

    n.physical = forbidden
    assert (await ws(conn, replies, "get", e))["success"]
    bad = await ws(
        conn, replies, "save", e, expected_epoch=n.epoch, expected_revision=True, policy=POLICY
    )
    assert not bad["success"] and bad["error"]["code"] == "notification_conflict"
    bad = await save(conn, replies, e, n, POLICY | {"cooldown_seconds": True})
    assert not bad["success"]
    bad = await ws(conn, replies, "ack", e, expected_epoch=n.epoch, event_id=n.epoch + ":1")
    assert not bad["success"] and not Path(n.store.path).exists()


async def test_actual_core_stop_retains_entered_write_until_settled(dosing_hass):
    import threading

    from homeassistant.const import EVENT_HOMEASSISTANT_STOP
    from homeassistant.core import Context

    from custom_components.uninus_nutriculture.notification_api import execute

    h = dosing_hass
    e, n, conn, replies = await ready(h)
    entered, release = threading.Event(), threading.Event()
    stop_entered, stop_release = asyncio.Event(), asyncio.Event()
    native = n.store._write_prepared_data

    def write(mode, data):
        entered.set()
        assert release.wait(10)
        return native(mode, data)

    n.store._write_prepared_data = write

    async def hold_stop(event):
        stop_entered.set()
        await stop_release.wait()

    unsub = h.bus.async_listen(EVENT_HOMEASSISTANT_STOP, hold_stop)
    task = asyncio.create_task(
        execute(
            h,
            Context(user_id=conn.user.id),
            "save",
            dict(
                config_entry_id=e.entry_id,
                expected_epoch=n.epoch,
                expected_revision=0,
                policy=POLICY,
            ),
        )
    )
    stop = None
    try:
        await until(entered.is_set)
        stop = asyncio.create_task(h.async_stop(force=True))
        await asyncio.wait_for(stop_entered.wait(), 2)
        task.cancel()
        await asyncio.sleep(0.03)
        task.cancel()
        drain = asyncio.create_task(n.drain())
        await asyncio.sleep(0.03)
        assert n.closed and n.lock.locked() and not task.done() and not drain.done(), dict(
            task_done=task.done(),
            task_cancelled=task.cancelled(),
            io=[repr(t) for t in n.io],
            release=release.is_set(),
            stored=Path(n.store.path).exists(),
            task_exception=repr(task.exception()) if task.done() and not task.cancelled() else None,
        )
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        await drain
        assert not n.lock.locked() and not n.io and n.indeterminate
        assert json.loads(Path(n.store.path).read_text())["data"]["revision"] == 1
        assert n.revision == 0
    finally:
        release.set()
        stop_release.set()
        unsub()
        if stop is not None:
            await stop


async def test_postwrite_principal_revocation_never_updates_cache(dosing_hass):
    import threading

    e, n, conn, replies = await ready(dosing_hass)
    entered, release = threading.Event(), threading.Event()
    native = n.store._write_prepared_data

    def write(mode, data):
        native(mode, data)
        entered.set()
        assert release.wait(10)

    n.store._write_prepared_data = write
    task = asyncio.create_task(save(conn, replies, e, n))
    try:
        await until(entered.is_set)
        conn.user.is_active = False
    finally:
        release.set()
    response = await task
    assert not response["success"] and response["error"]["code"] == "unauthorized"
    assert n.indeterminate and n.revision == 0
    assert json.loads(Path(n.store.path).read_text())["data"]["revision"] == 1


async def test_cancelled_drain_settles_io_then_preserves_cancellation(dosing_hass):
    import threading

    from homeassistant.core import Context

    from custom_components.uninus_nutriculture.notification_api import execute

    e, n, conn, replies = await ready(dosing_hass)
    entered, release = threading.Event(), threading.Event()
    native = n.store._write_prepared_data

    def write(mode, data):
        entered.set()
        assert release.wait(10)
        return native(mode, data)

    n.store._write_prepared_data = write
    task = asyncio.create_task(
        execute(
            dosing_hass,
            Context(user_id=conn.user.id),
            "save",
            dict(
                config_entry_id=e.entry_id,
                expected_epoch=n.epoch,
                expected_revision=0,
                policy=POLICY,
            ),
        )
    )
    drain = None
    try:
        await until(entered.is_set)
        drain = asyncio.create_task(n.drain())
        await asyncio.sleep(0.01)
        drain.cancel()
        await asyncio.sleep(0.01)
        drain.cancel()
        await asyncio.sleep(0.01)
        assert not drain.done() and n.lock.locked()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await drain
    await task
    assert not n.io and n.indeterminate


async def test_cancelled_native_load_keeps_quarantine_and_drains(dosing_hass):
    import threading

    from homeassistant.core import Context

    from custom_components.uninus_nutriculture.notification_api import execute

    e, n, conn, replies = await ready(dosing_hass)
    assert (await save(conn, replies, e, n))["success"]
    native = n.physical
    entered, release = threading.Event(), threading.Event()

    def read():
        entered.set()
        assert release.wait(10)
        return native()

    n.physical = read
    task = asyncio.create_task(
        execute(
            dosing_hass,
            Context(user_id=conn.user.id),
            "reconcile",
            dict(config_entry_id=e.entry_id, expected_epoch=n.epoch),
        )
    )
    try:
        await until(entered.is_set)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done() and n.lock.locked()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    n.physical = native
    assert n.indeterminate and not n.io and not n.lock.locked()
    assert (await ws(conn, replies, "reconcile", e, expected_epoch=n.epoch))["success"]


async def test_setup_corrupt_policy_stays_disabled_quarantined(dosing_hass):
    h = dosing_hass
    e, n, conn, replies = await ready(h)
    assert (await save(conn, replies, e, n))["success"]
    raw = json.loads(Path(n.store.path).read_text())
    raw["data"]["policy"]["secret_canary"] = "secret_canary"
    Path(n.store.path).write_text(json.dumps(raw))
    assert await h.config_entries.async_reload(e.entry_id)
    dto = e.runtime_data.notifications.dto()
    assert dto["availability"] == "indeterminate" and not dto["policy"]["enabled"]
    assert "secret_canary" not in str(dto)
