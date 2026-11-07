import asyncio
import json
import os
from pathlib import Path

import pytest
from aiohttp.test_utils import make_mocked_request
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.config.config_entries import OptionManagerFlowResourceView
from test_p3_dosing import dosing_hass as dosing_hass
from test_p4c_completion import sink_runtime
from test_p4c_notifications import ws


@pytest.mark.parametrize("change", ["role", "delete", "owner"])
async def test_native_options_http_admitted_then_revoked_does_not_reserialize_private_cache(
    dosing_hass, monkeypatch, change
):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    user = await h.auth.async_create_user("inflight Options admin", group_ids=[GROUP_ID_ADMIN])
    c.user = user
    f = await h.config_entries.options.async_init(e.entry_id, context={"user_id": user.id})
    f = await h.config_entries.options.async_configure(
        f["flow_id"],
        {
            **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            "notification_management": True,
        },
    )
    assert f["step_id"] == "notifications" and user.is_admin
    before = Path(n.store.path).read_bytes()
    owner = e.runtime_data
    # Native HTTP view decorators run as authorized; revoke only inside its awaited shared auth.
    entered = asyncio.Event()
    release = asyncio.Event()
    original = h.auth.async_get_user

    async def held(self, ident):
        if ident == user.id:
            entered.set()
            await release.wait()
        return await original(ident)

    monkeypatch.setattr(type(h.auth), "async_get_user", held)
    payload = dict(
        enabled=True,
        provider="notify_entity",
        events=["start"],
        cooldown_seconds=60,
        action="reconcile",
    )
    request = make_mocked_request(
        "POST",
        "/api/config/config_entries/options/flow/" + f["flow_id"],
        headers={"Content-Type": "application/json"},
    )
    request["hass_user"] = user
    request._read_bytes = json.dumps(payload).encode()
    view = OptionManagerFlowResourceView(h.config_entries.options)
    task = asyncio.create_task(view.post(request, f["flow_id"]))
    await asyncio.wait_for(entered.wait(), 2)
    try:
        if change == "role":
            user.groups = []
        elif change == "delete":
            await h.auth.async_remove_user(user)
        else:
            e.runtime_data = object()
    finally:
        release.set()
    try:
        response = await asyncio.wait_for(task, 3)
        body = json.loads(response.body)
        denial = await ws(c, replies, "get", e)
        assert not denial["success"]
        assert Path(n.store.path).read_bytes() == before
        record = {
            "change": change,
            "http_status": response.status,
            "body": body,
            "submitted": payload,
            "private_target": sink.entity_id,
            "private_binding": n.policy["target_binding"],
            "native_denied_get": denial,
            "same_user_id": user.id,
            "before_revision": n.revision,
            "entry_id": e.entry_id,
            "epoch": n.epoch,
            "no_disk_mutation": True,
            "no_actuator_calls": not h.data["p2_fixture"]["calls"]
            and not h.data["p3_fixture"]["calls"],
        }
        if directory := os.environ.get("GATE_OUT"):
            out = Path(directory)
            out.mkdir(parents=True, exist_ok=True)
            (out / ("native-options-inflight-" + change + ".json")).write_text(
                json.dumps(record, indent=2), encoding="utf-8"
            )
        assert record["no_actuator_calls"] and not sink.messages
        assert body["type"] == "abort"
        assert sink.entity_id not in json.dumps(body), (
            "Native Options serialized saved private target after in-flight "
            + change
            + " revocation"
        )
    finally:
        e.runtime_data = owner


async def open_private(h, e, user):
    f = await h.config_entries.options.async_init(e.entry_id, context={"user_id": user.id})
    return await h.config_entries.options.async_configure(
        f["flow_id"],
        {
            **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            "notification_management": True,
        },
    )


def submission(**changes):
    return (
        dict(
            enabled=True,
            provider="notify_entity",
            events=["start"],
            cooldown_seconds=60,
            action="reconcile",
        )
        | changes
    )


@pytest.mark.parametrize("change", ["role", "delete", "owner"])
@pytest.mark.parametrize("branch", ["cached_get", "provider"])
async def test_cached_readonly_branches_retire_private_draft(dosing_hass, change, branch):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    user = await h.auth.async_create_user("cached admin", group_ids=[GROUP_ID_ADMIN])
    c.user = user
    groups = list(user.groups)
    owner = e.runtime_data
    f = await open_private(h, e, user)
    if branch == "provider":
        f = await h.config_entries.options.async_configure(
            f["flow_id"], submission(provider="persistent_notification")
        )
        assert "target_entity_id" not in {str(k) for k in f["data_schema"].schema}
    flow = h.config_entries.options._progress[f["flow_id"]]
    before = Path(n.store.path).read_bytes()
    try:
        if change == "role":
            user.groups = []
        elif change == "delete":
            await h.auth.async_remove_user(user)
        else:
            e.runtime_data = object()
        payload = None if branch == "cached_get" else submission(action="save")
        # Native Options manager, bypass no serializer/auth methods; no target in payload.
        f = await h.config_entries.options.async_configure(f["flow_id"], payload)
        assert f["type"] == "abort"
        assert sink.entity_id not in str(f)
        assert getattr(flow, "_notification_dto", None) is None
        assert not getattr(flow, "_notification_fields", set())
        assert Path(n.store.path).read_bytes() == before
        assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
        assert not sink.messages
        if change == "role":
            user.groups = groups
            assert (await flow.async_step_notifications())["type"] == "abort"
            assert getattr(flow, "_notification_dto", None) is None
            fresh = await open_private(h, e, user)
            assert fresh["type"] == "form"
            assert target_suggestion(fresh) == sink.entity_id
    finally:
        e.runtime_data = owner


@pytest.mark.parametrize("stale", ["revision", "epoch"])
async def test_fresh_authority_never_rebases_options_cas(dosing_hass, stale):
    from test_p4c_completion import policy

    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    f = await open_private(h, e, c.user)
    if stale == "revision":
        await policy(c, replies, e, enabled=False)
    else:
        e.runtime_data.results.rotate_epoch()
    before = Path(n.store.path).read_bytes()
    revision = n.revision
    f = await h.config_entries.options.async_configure(
        f["flow_id"], submission(action="save", target_entity_id=sink.entity_id)
    )
    assert f.get("reason", f.get("errors", {}).get("base")) == "notification_conflict"
    assert Path(n.store.path).read_bytes() == before and n.revision == revision
    assert not sink.messages


async def test_valid_reconcile_cancel_and_validation_keep_options_usable(dosing_hass):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    f = await open_private(h, e, c.user)
    before = Path(n.store.path).read_bytes()
    f = await h.config_entries.options.async_configure(
        f["flow_id"], submission(action="save", target_entity_id="notify.missing")
    )
    assert f["type"] == "form" and f["errors"]
    f = await h.config_entries.options.async_configure(f["flow_id"], submission())
    assert f["type"] == "form" and not f["errors"]
    assert target_suggestion(f) == sink.entity_id
    f = await h.config_entries.options.async_configure(f["flow_id"], submission(action="cancel"))
    assert f["type"] == "abort" and f["reason"] == "notification_cancelled"
    assert Path(n.store.path).read_bytes() == before and not sink.messages


def target_suggestion(form):
    return next(
        k.description["suggested_value"]
        for k in form["data_schema"].schema
        if str(k) == "target_entity_id"
    )
