"""Native read-side withdrawal must publish without recursive serialization."""

import asyncio
from copy import deepcopy

import pytest
import pytest_asyncio
from homeassistant.core import CoreState
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import target
from test_p3_dosing import dosing_hass as dosing_hass
from test_p4b_native import api
from test_p4b_permit import completed, reports


@pytest_asyncio.fixture
async def granted(dosing_hass):
    h = dosing_hass
    e, ctx = await completed(h)
    q = e.runtime_data.quality
    try:
        await reports(h)
        await asyncio.sleep(1.02)
        await reports(h)
        dto = await api(h, ctx, e)
        assert dto["permit"]["granted"]
        assert dto["policy"]["permit_ttl_seconds"] == 2
        assert q.clock == h.loop.time
        assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "on"
        yield h, e, ctx, q
    finally:
        q.close()
        await asyncio.wait_for(e.runtime_data.control.stop(), 10)
        await asyncio.wait_for(h.async_stop(force=True), 15)
        assert h.state is CoreState.stopped


def native(h, e):
    return (
        h.states.get(target(h, e, "binary_sensor", "irrigation_permit")),
        h.states.get(target(h, e, "sensor", "quality_status")),
    )


async def due_before_callback(h, q):
    hard = q.hard
    await asyncio.sleep(max(0, hard - 0.020 - h.loop.time()))
    timer = q.timer
    assert q.granted and q.hard == hard and timer and not timer.cancelled()
    assert h.loop.time() < hard and timer.when() == hard
    start = h.loop.time()
    while h.loop.time() < hard and h.loop.time() - start < 0.030:
        pass
    assert h.loop.time() >= hard and h.loop.time() - start <= 0.035
    assert q.granted
    return timer


async def coherent(h, e, ctx, q):
    binary, quality = native(h, e)
    # Native observations precede API reads: the observer cannot repair the candidate.
    assert binary.state == "off", "native OFF after withdrawal and fixed 0.150s yield"
    assert not quality.attributes["permit"]["granted"]
    revision = q.observation_revision
    assert binary.attributes["observation_revision"] == revision
    assert quality.attributes["observation_revision"] == revision
    if not e.runtime_data.active:
        with pytest.raises(ServiceValidationError, match="entry_not_loaded"):
            await api(h, ctx, e)
        return
    dto = await api(h, ctx, e)
    assert not dto["permit"]["granted"]
    assert dto["observation_revision"] == revision


async def test_due_read_before_expiry_callback(granted):
    h, e, ctx, q = granted
    timer = await due_before_callback(h, q)
    dto = q.dto()
    assert not dto["permit"]["granted"] and not q.granted
    assert timer.cancelled()
    await asyncio.sleep(0.150)
    await coherent(h, e, ctx, q)


async def test_ordinary_expiry_without_get(granted):
    h, e, ctx, q = granted
    await asyncio.sleep(max(0, q.hard - h.loop.time()) + 0.150)
    await coherent(h, e, ctx, q)


async def test_native_serialization_withdrawal_is_not_recursive(granted):
    h, e, ctx, q = granted
    await due_before_callback(h, q)
    entity = next(
        listener.__self__
        for listener in e.runtime_data.listeners
        if getattr(getattr(listener, "__self__", None), "entity_id", None)
        == target(h, e, "sensor", "quality_status")
    )
    entity.async_write_ha_state()
    assert not q.granted
    await asyncio.sleep(0.150)
    await coherent(h, e, ctx, q)


async def test_repeated_reads_do_not_extend_revive_or_repeat_notify(granted):
    h, e, ctx, q = granted
    hard = q.hard
    for _ in range(20):
        assert q.dto()["permit"]["granted"] and q.hard == hard
    await due_before_callback(h, q)
    calls = []
    original = q.notify

    def observer():
        calls.append(h.loop.time())
        original()

    q.notify = observer
    try:
        for _ in range(20):
            assert not q.dto()["permit"]["granted"]
        await asyncio.sleep(0.150)
        await coherent(h, e, ctx, q)
        assert len(calls) == 1
        for _ in range(20):
            assert not q.dto()["permit"]["granted"]
        await asyncio.sleep(0.150)
        assert len(calls) == 1 and q.hard is None and q.candidate is None
    finally:
        q.notify = original


@pytest.mark.parametrize("cause", ["health", "settings", "capability"])
async def test_read_side_guard_withdrawal_publishes(granted, cause):
    h, e, ctx, q = granted
    if cause == "health":
        q.regressed.add("ph")
    elif cause == "settings":
        options = deepcopy(dict(e.options))
        options["settings_revision"] = options.get("settings_revision", 0) + 1
        h.config_entries.async_update_entry(e, options=options)
    else:
        e.runtime_data.active = False
    assert not q.dto()["permit"]["granted"]
    await asyncio.sleep(0.150)
    await coherent(h, e, ctx, q)


async def test_close_retires_pending_read_notification(granted):
    h, e, _, q = granted
    await due_before_callback(h, q)
    calls = []
    original = q.notify

    def observer():
        calls.append(h.loop.time())
        original()

    q.notify = observer
    try:
        assert not q.dto()["permit"]["granted"]
        q.close()
        at_close = len(calls)
        assert at_close == 1
        await asyncio.sleep(0.150)
        assert len(calls) == at_close and q.closed
        assert native(h, e)[0].state == "off"
    finally:
        q.notify = original
