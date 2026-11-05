"""Native grant expiry projection: exact equality, independent monotonic safety."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from homeassistant.util import dt as dt_util
from test_p2_control import target
from test_p3_dosing import dosing_hass as dosing_hass
from test_p4b_native import api
from test_p4b_permit import completed, reports


async def granted(h):
    e, ctx = await completed(h)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    dto = await api(h, ctx, e)
    assert dto["permit"]["granted"] is True
    return e, ctx, dto


@pytest.mark.parametrize("order", ["publisher_first", "api_first", "alternating"])
async def test_same_authority_exact_expiry_across_native_and_api(dosing_hass, monkeypatch, order):
    h = dosing_hass
    e, ctx, initial = await granted(h)
    q = e.runtime_data.quality
    module = __import__(q.__class__.__module__, fromlist=["dt_util"])
    before = (q.epoch, q.observation_revision, q.hard, dict(q.samples), q.count, q.first, q.last)
    clock = q.clock
    mono = clock()
    utc = dt_util.utcnow()
    ticks = 0

    def advancing_utc():
        nonlocal ticks
        ticks += 1
        return utc + timedelta(microseconds=101 * ticks)

    def native():
        q.notify()
        return dict(h.states.get(target(h, e, "sensor", "quality_status")).attributes)

    try:
        # Only this integration's UTC reference and explicit domain clock seam;
        # Core Auth/Store/state clocks remain real. The bounded seam is restored.
        q.clock = lambda: mono
        with monkeypatch.context() as patch:
            patch.setattr(module, "dt_util", SimpleNamespace(utcnow=advancing_utc))
            frames = []
            for index in range(3):
                first = order == "publisher_first" or (order == "alternating" and index % 2 == 0)
                if first:
                    frames.extend([native(), await api(h, ctx, e)])
                else:
                    frames.extend([await api(h, ctx, e), native()])
            assert all(d["permit"]["granted"] is True for d in frames)
            assert all((d["epoch"], d["observation_revision"]) == before[:2] for d in frames)
            assert {d["permit"]["expires_at"] for d in frames} == {
                initial["permit"]["expires_at"]
            }, "unchanged native/API authority must project one exact expiry"
            assert ticks > 6
        assert (
            q.epoch,
            q.observation_revision,
            q.hard,
            dict(q.samples),
            q.count,
            q.first,
            q.last,
        ) == before
        assert datetime.fromisoformat(initial["permit"]["expires_at"]).tzinfo is not None
    finally:
        q.clock = clock
        q.schedule()


@pytest.mark.parametrize("route", ["getter", "timer"])
async def test_utc_drift_cannot_move_exact_monotonic_expiration(dosing_hass, monkeypatch, route):
    h = dosing_hass
    e, ctx, initial = await granted(h)
    q = e.runtime_data.quality
    module = __import__(q.__class__.__module__, fromlist=["dt_util"])
    hard = q.hard
    samples = dict(q.samples)
    clock = q.clock
    utc = dt_util.utcnow()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(
                module, "dt_util", SimpleNamespace(utcnow=lambda: utc + timedelta(seconds=0.1))
            )
            q.clock = lambda: hard - 0.000001
            before = await api(h, ctx, e)
            assert before["permit"] == initial["permit"]
            assert q.hard == hard and q.samples == samples
            q.clock = lambda: hard
            if route == "timer":
                q.expire()
            expired = await api(h, ctx, e)
            assert expired["permit"]["granted"] is False
            assert expired["permit"]["expires_at"] is None
            q.clock = lambda: hard + 0.000001
            assert (await api(h, ctx, e))["permit"]["granted"] is False
    finally:
        q.clock = clock
        q.schedule()
    await reports(h)
    after = await api(h, ctx, e)
    assert after["permit"]["granted"] is False
    assert after["permit"]["expires_at"] is None


async def test_new_reports_keep_hard_projection_then_revocation_clears_it(dosing_hass):
    h = dosing_hass
    e, ctx, initial = await granted(h)
    q = e.runtime_data.quality
    hard = q.hard
    previous_samples = dict(q.samples)
    await reports(h)
    fresh = await api(h, ctx, e)
    assert fresh["observation_revision"] > initial["observation_revision"]
    assert q.samples != previous_samples
    assert q.hard == hard
    assert fresh["permit"] == initial["permit"]
    h.states.async_set("sensor.ph", "unavailable")
    await h.async_block_till_done()
    revoked = await api(h, ctx, e)
    assert revoked["observation_revision"] > fresh["observation_revision"]
    assert revoked["permit"]["granted"] is False
    assert revoked["permit"]["expires_at"] is None
    assert h.states.get(target(h, e, "binary_sensor", "irrigation_permit")).state == "off"


async def test_changed_freshness_deadline_gets_one_new_projection(dosing_hass, monkeypatch):
    import test_p4b_permit as helper

    original = helper.policy

    async def long_ttl(h, e, ctx, **changes):
        return await original(h, e, ctx, **{**changes, "permit_ttl_seconds": 600})

    # Use the normal registered policy save before the actual full run, not
    # injected grants/deadlines. Freshness, not hard TTL, now binds the permit.
    monkeypatch.setattr(helper, "policy", long_ttl)
    h = dosing_hass
    e, ctx, initial = await granted(h)
    q = e.runtime_data.quality
    old_deadline = q.deadline()
    pair = (q._projection_utc, q._projection_monotonic)
    hard = q.hard
    await reports(h)
    newer = await api(h, ctx, e)
    q.notify()
    native = h.states.get(target(h, e, "sensor", "quality_status")).attributes
    assert q.deadline() > old_deadline
    assert q.hard == hard
    assert (q._projection_utc, q._projection_monotonic) == pair
    assert newer["observation_revision"] > initial["observation_revision"]
    assert newer["permit"]["expires_at"] != initial["permit"]["expires_at"]
    assert newer["permit"] == native["permit"]
    assert newer["permit"] == (await api(h, ctx, e))["permit"]


async def test_real_clock_native_api_exact_equality_without_clock_patch(dosing_hass):
    h = dosing_hass
    e, ctx, initial = await granted(h)
    q = e.runtime_data.quality
    hard = q.hard
    samples = dict(q.samples)
    pair = (q._projection_utc, q._projection_monotonic)
    for _ in range(4):
        await asyncio.sleep(0.003)
        q.notify()
        native = h.states.get(target(h, e, "sensor", "quality_status")).attributes
        actual = await api(h, ctx, e)
        assert actual["permit"] == native["permit"] == initial["permit"]
        assert actual["observation_revision"] == initial["observation_revision"]
        assert q.hard == hard and q.samples == samples
        assert (q._projection_utc, q._projection_monotonic) == pair
