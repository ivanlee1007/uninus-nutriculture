"""R1 A/B native regressions; single-slot scope, not the full P5 matrix."""

import asyncio
from copy import deepcopy

import pytest
from homeassistant.helpers import entity_registry as er
from test_p2_control import target
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5, until
from test_p4b_native import api, owner
from test_p4b_permit import completed, policy, reports


async def grant(h):
    e, ctx = await completed(h)
    await reports(h)
    await asyncio.sleep(1.02)
    await reports(h)
    assert (await api(h, ctx, e))["permit"]["granted"] is True
    return e, ctx


async def test_sequence_forward_then_regression_latches_only_affected_source(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    sources = deepcopy((await api(h, ctx, e))["policy"]["sources"])
    for row in sources.values():
        row.update(mode="sequence", attribute="measurement", report_contract_confirmed=True)
    await policy(h, e, ctx, sources=sources)
    q = e.runtime_data.quality

    async def send(tokens):
        for key, value, unit in (("ph", 5.6, "pH"), ("ec", 0.87, "mS/cm"), ("level", 2.4, "m")):
            h.states.async_set(
                "sensor." + key,
                value,
                {"unit_of_measurement": unit, "measurement": tokens[key]},
            )
        await h.async_block_till_done()
        return await api(h, ctx, e)

    assert (await send(dict(ph=5, ec=5, level=5)))["quality"]["stable_count"] == 1
    await asyncio.sleep(1.02)
    assert (await send(dict(ph=6, ec=6, level=6)))["quality"]["state"] == "qualified"
    d = await send(dict(ph=4, ec=7, level=7))
    assert d["quality"] == dict(
        state="invalid", stable_count=0, stable_since=None, reasons=["sample_regressed"]
    )
    assert q.regressed == {"ph"}
    assert q.tokens["ec"] == 7 and q.tokens["level"] == 7
    d = await send(dict(ph=8, ec=8, level=8))
    assert d["quality"]["state"] == "invalid"
    assert d["quality"]["reasons"] == ["sample_regressed"]
    assert d["quality"]["stable_count"] == 0
    assert d["permit"]["granted"] is False
    assert q.regressed == {"ph"}


@pytest.mark.parametrize("phase", ["preterminal", "granted"])
async def test_unrelated_registry_create_update_preserves_authority(dosing_hass, phase):
    h = dosing_hass
    task = asyncio.create_task(completed(h)) if phase == "preterminal" else None
    if task:

        def active():
            return next(
                (
                    e
                    for e in h.config_entries.async_entries("uninus_nutriculture")
                    if getattr(e, "runtime_data", None)
                    and e.runtime_data.quality.completion["state"] == "running"
                ),
                None,
            )

        await until(lambda: active() is not None)
        e = active()
    else:
        e, ctx = await grant(h)
    q = e.runtime_data.quality
    before = (q.epoch, q.candidate, q.consumed, q.count, q.first, q.hard)
    registry = er.async_get(h)
    row = registry.async_get_or_create("sensor", "test", "r1-unrelated")
    registry.async_update_entity(row.entity_id, name="unrelated update")
    await asyncio.sleep(0.03)
    assert (q.epoch, q.candidate, q.consumed, q.count, q.first, q.hard) == before
    if task:
        e, ctx = await task
        await reports(h)
        await asyncio.sleep(1.02)
        await reports(h)
    assert (await api(h, ctx, e))["permit"]["granted"] is True


@pytest.mark.parametrize("action", ["remove", "disable", "rename", "replace"])
async def test_foreign_bound_output_registry_loss_revokes_without_revival(dosing_hass, action):
    h = dosing_hass
    e, ctx = await grant(h)
    q = e.runtime_data.quality
    registry = er.async_get(h)
    binding = e.options["control"]["binding"]
    row = next(row for row in registry.entities.values() if row.id == binding["registry_id"])
    assert row.platform != "uninus_nutriculture"
    epoch = q.epoch
    if action == "remove":
        registry.async_remove(row.entity_id)
        assert registry.async_get(row.entity_id) is None
    elif action == "disable":
        registry.async_update_entity(row.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    elif action == "rename":
        registry.async_update_entity(row.entity_id, new_entity_id="switch.r1_renamed_output")
    else:
        registry.async_update_entity(row.entity_id, new_unique_id="r1-replaced-identity")
    await asyncio.sleep(0.03)
    # Check callback effects BEFORE any getter can conceal a missed registry event.
    assert not q.granted and q.candidate is None and q.consumed
    assert q.epoch != epoch
    if action == "disable":
        registry.async_update_entity(row.entity_id, disabled_by=None)
    await reports(h)
    assert (await api(h, ctx, e))["permit"]["granted"] is False
    assert q.candidate is None


@pytest.mark.parametrize("kind", ["source", "permit", "quality"])
async def test_slot_registry_removal_revokes_immediately(dosing_hass, kind):
    h = dosing_hass
    registry = er.async_get(h)
    if kind == "source":
        # Reserve the real configured ID before the fixture restores telemetry.
        previous = h.states.get("sensor.ph")
        h.states.async_remove("sensor.ph")
        row = registry.async_get_or_create("sensor", "test", "r1-source", suggested_object_id="ph")
        assert row.entity_id == "sensor.ph"
        h.states.async_set("sensor.ph", previous.state, dict(previous.attributes))
    e, ctx = await grant(h)
    identity = (
        "sensor.ph"
        if kind == "source"
        else target(
            h,
            e,
            "binary_sensor" if kind == "permit" else "sensor",
            "irrigation_permit" if kind == "permit" else "quality_status",
        )
    )
    q = e.runtime_data.quality
    epoch = q.epoch
    registry.async_remove(identity)
    assert registry.async_get(identity) is None
    await asyncio.sleep(0.03)
    assert not q.granted and q.candidate is None and q.consumed
    assert q.epoch != epoch
    await reports(h)
    assert (await api(h, ctx, e))["permit"]["granted"] is False


async def test_source_registry_disabled_after_grant(dosing_hass):
    h = dosing_hass
    registry = er.async_get(h)
    previous = h.states.get("sensor.ph")
    h.states.async_remove("sensor.ph")
    row = registry.async_get_or_create(
        "sensor", "test", "r1-source-disabled", suggested_object_id="ph"
    )
    assert row.entity_id == "sensor.ph"
    h.states.async_set("sensor.ph", previous.state, dict(previous.attributes))
    e, ctx = await grant(h)
    epoch = e.runtime_data.quality.epoch
    registry.async_update_entity(row.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await asyncio.sleep(0.03)
    assert e.runtime_data.quality.epoch != epoch
    assert not e.runtime_data.quality.granted
    registry.async_update_entity(row.entity_id, disabled_by=None)
    await reports(h)
    assert not (await api(h, ctx, e))["permit"]["granted"]
