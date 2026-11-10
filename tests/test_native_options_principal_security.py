"""Same-root security and write-path regressions; no live HA or client identity trust."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from aiohttp.test_utils import make_mocked_request
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.helpers.http import KEY_HASS, current_request
from test_native_options_principal import BASE, headers, native_http, open_http
from test_p3_dosing import dosing_hass as dosing_hass
from test_p4c_completion import sink_runtime

KINDS = ["quality", "recipe", "notification"]
STEPS = {"quality": "quality", "recipe": "recipes", "notification": "notifications"}


def defaults(form, **changes):
    return {
        **{field["name"]: field["default"] for field in form["data_schema"] if "default" in field},
        **changes,
    }


def projection_spies(monkeypatch, e, n):
    from custom_components.uninus_nutriculture import recipes

    calls = []
    for obj, key in [(recipes, "dto"), (type(e.runtime_data.quality), "dto"), (type(n), "dto")]:
        original = getattr(obj, key)

        def observe(*args, _original=original, **kwargs):
            calls.append(_original.__qualname__)
            return _original(*args, **kwargs)

        monkeypatch.setattr(obj, key, observe)
    return calls


def private_cleared(flow):
    assert all(
        getattr(flow, key, None) is None
        for key in (
            "_quality_dto",
            "_recipe_dto",
            "_recipe_draft",
            "_recipe_identity",
            "_notification_dto",
            "_notification_owner",
            "_options_owner",
        )
    )
    assert not getattr(flow, "_notification_fields", set())


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "change",
    [
        "actor",
        "forged_context",
        "owner",
        "missing_request",
        "unauthenticated_request",
        "missing_request_user",
        "late_role",
        "late_delete",
        "late_system",
    ],
)
async def test_native_private_followup_denies_before_projection_and_retires(
    dosing_hass, monkeypatch, kind, change
):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    user = await h.auth.async_create_user("flow human", group_ids=[GROUP_ID_ADMIN])
    other = await h.auth.async_create_user("different admin", group_ids=[GROUP_ID_ADMIN])
    async with native_http(h) as client:
        form, flow, auth = await open_http(client, h, e, user, kind)
        assert form["type"] == "form" and not form["errors"]
        owner = e.runtime_data
        options = deepcopy(dict(e.options))
        durable = Path(n.store.path).read_bytes()
        calls = projection_spies(monkeypatch, e, n)
        groups = list(user.groups)
        try:
            if change == "actor":
                auth = await headers(h, other)
            elif change == "forged_context":
                flow.context["user_id"] = other.id
            elif change == "owner":
                e.runtime_data = object()
            elif change.startswith("late_"):
                original = h.auth.async_get_user

                async def revoke(manager, ident):
                    found = await original(ident)
                    if ident == user.id:
                        if change == "late_role":
                            user.groups = []
                        elif change == "late_system":
                            user.system_generated = True
                        else:
                            await h.auth.async_remove_user(user)
                            return None
                    return found

                monkeypatch.setattr(type(h.auth), "async_get_user", revoke)
            if change in ("missing_request", "unauthenticated_request", "missing_request_user"):
                request = None
                if change != "missing_request":
                    request = make_mocked_request("GET", BASE, app={KEY_HASS: h})
                    request["ha_authenticated"] = change != "unauthenticated_request"
                    if change != "missing_request_user":
                        request["hass_user"] = user
                token = current_request.set(request)
                try:
                    body = await getattr(flow, "async_step_" + STEPS[kind])()
                finally:
                    current_request.reset(token)
            else:
                response = await client.get(BASE + "/" + form["flow_id"], headers=auth)
                assert response.status == 200, await response.text()
                body = await response.json()
            assert body["type"] == "abort", body
            assert body["reason"] in ("unauthorized", "entry_not_loaded")
            assert not calls, "denial crossed protected projection boundary"
            private_cleared(flow)
            assert sink.entity_id not in str(body)
            assert dict(e.options) == options
            assert Path(n.store.path).read_bytes() == durable
            assert not sink.messages
            assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
            # Restoration cannot revive this retired private flow.
            monkeypatch.undo()
            e.runtime_data = owner
            user.groups = groups
            user.system_generated = False
            flow.context.pop("user_id", None)
            assert (await getattr(flow, "async_step_" + STEPS[kind])())["type"] == "abort"
            private_cleared(flow)
        finally:
            e.runtime_data = owner


@pytest.mark.parametrize("kind", KINDS)
async def test_http_init_actor_is_bound_before_private_navigation(dosing_hass, monkeypatch, kind):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    first = await h.auth.async_create_user("first", group_ids=[GROUP_ID_ADMIN])
    second = await h.auth.async_create_user("second", group_ids=[GROUP_ID_ADMIN])
    async with native_http(h) as client:
        response = await client.post(
            BASE, json={"handler": e.entry_id}, headers=await headers(h, first)
        )
        assert response.status == 200
        form = await response.json()
        flow = h.config_entries.options._progress[form["flow_id"]]
        calls = projection_spies(monkeypatch, e, n)
        payload = {
            **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            kind + "_management": True,
        }
        # Client-supplied identity is rejected by Core's form schema, not consumed.
        response = await client.post(
            BASE + "/" + form["flow_id"],
            json={**payload, "user_id": first.id},
            headers=await headers(h, second),
        )
        assert response.status == 400
        assert not calls
        response = await client.post(
            BASE + "/" + form["flow_id"],
            json=payload,
            headers=await headers(h, second),
        )
        assert response.status == 200
        body = await response.json()
        assert body["type"] == "abort" and body["reason"] == "unauthorized"
        assert not calls
        private_cleared(flow)


@pytest.mark.parametrize("identity", ["anonymous", "nonadmin", "system"])
async def test_native_http_initial_human_restrictions(dosing_hass, monkeypatch, identity):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    create = h.auth.async_create_system_user if identity == "system" else h.auth.async_create_user
    user = await create(
        "blocked actor", group_ids=[] if identity == "nonadmin" else [GROUP_ID_ADMIN]
    )
    async with native_http(h) as client:
        auth = {} if identity == "anonymous" else await headers(h, user)
        calls = projection_spies(monkeypatch, e, n)
        response = await client.post(
            BASE, json={"handler": e.entry_id, "user_id": c.user.id}, headers=auth
        )
        if identity == "system":
            assert response.status == 200
            body = await response.json()
            assert body["type"] == "abort" and body["reason"] == "unauthorized"
        else:
            assert response.status == 401
        assert not calls


@pytest.mark.parametrize("kind", KINDS)
async def test_native_http_authorized_save_reopen(dosing_hass, kind):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    user = await h.auth.async_create_user("saving human", group_ids=[GROUP_ID_ADMIN])
    async with native_http(h) as client:
        form, flow, auth = await open_http(client, h, e, user, kind)
        assert form["type"] == "form" and not form["errors"]
        if kind == "recipe":
            response = await client.post(
                BASE + "/" + form["flow_id"], json={"action": "new", "recipe_id": ""}, headers=auth
            )
            assert response.status == 200
            form = await response.json()
            assert form["step_id"] == "recipe_edit" and not form["errors"]
            payload = defaults(form, action="save", name="HTTP durable recipe")
        elif kind == "quality":
            payload = defaults(form, action="save", stable_samples=2)
        else:
            payload = defaults(
                form, action="save", cooldown_seconds=61, target_entity_id=sink.entity_id
            )
        response = await client.post(BASE + "/" + form["flow_id"], json=payload, headers=auth)
        assert response.status == 200, await response.text()
        body = await response.json()
        assert not body.get("errors"), body
        if kind == "quality":
            assert body["reason"] == "quality_saved"
            assert e.options["quality_policy"]["stable_samples"] == 2
        elif kind == "recipe":
            assert body["step_id"] == "recipes"
            assert e.options["recipe_catalog"]["recipes"][0]["name"] == "HTTP durable recipe"
        else:
            assert body["reason"] == "notification_saved"
            assert n.policy["cooldown_seconds"] == 61
            assert (
                json.loads(Path(n.store.path).read_text())["data"]["policy"]["cooldown_seconds"]
                == 61
            )
        reopened, _, _ = await open_http(client, h, e, user, kind)
        assert reopened["step_id"] == STEPS[kind] and not reopened["errors"]
    assert not sink.messages
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


@pytest.mark.parametrize("kind", KINDS)
async def test_native_http_save_waiter_rechecks_human_before_first_mutation(
    dosing_hass, monkeypatch, kind
):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    user = await h.auth.async_create_user("queued saving human", group_ids=[GROUP_ID_ADMIN])
    assert user.is_admin and not user.is_owner
    async with native_http(h) as client:
        form, flow, auth = await open_http(client, h, e, user, kind)
        if kind == "recipe":
            response = await client.post(
                BASE + "/" + form["flow_id"], json={"action": "new", "recipe_id": ""}, headers=auth
            )
            form = await response.json()
            assert form["step_id"] == "recipe_edit" and not form["errors"]
            payload = defaults(form, action="save", name="Must not be saved")
        elif kind == "quality":
            payload = defaults(form, action="save", stable_samples=2)
        else:
            payload = defaults(
                form, action="save", cooldown_seconds=61, target_entity_id=sink.entity_id
            )
        options = deepcopy(dict(e.options))
        durable = Path(n.store.path).read_bytes()
        lock = n.lock if kind == "notification" else e.runtime_data.lock
        await lock.acquire()
        task = asyncio.create_task(
            client.post(BASE + "/" + form["flow_id"], json=payload, headers=auth)
        )
        try:
            async with asyncio.timeout(3):
                while not lock._waiters or not any(not waiter.done() for waiter in lock._waiters):
                    assert not task.done(), "Save never reached its real admission lock"
                    await asyncio.sleep(0.001)
            calls = projection_spies(monkeypatch, e, n)
            user.groups = []
            assert not user.is_admin
        finally:
            lock.release()
        response = await asyncio.wait_for(task, 3)
        assert response.status == 200
        body = await response.json()
        assert body["type"] == "abort" and body["reason"] == "unauthorized", body
        assert not calls
        private_cleared(flow)
        assert dict(e.options) == options
        assert Path(n.store.path).read_bytes() == durable
    assert not sink.messages
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
