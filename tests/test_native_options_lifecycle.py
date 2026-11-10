"""Real Core unload fences cached native Options without replacing its owner."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import UnknownFlow
from test_native_options_principal import BASE, headers, native_http, open_http
from test_native_options_principal_security import private_cleared, projection_spies
from test_p3_dosing import dosing_hass as dosing_hass
from test_p4c_completion import sink_runtime


@pytest.mark.parametrize("kind", ["quality", "recipe"])
@pytest.mark.parametrize("operation", ["cached_get", "save_error"])
async def test_unloading_same_owner_must_retire(
    dosing_hass, monkeypatch, tmp_path, kind, operation
):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    user = await h.auth.async_create_user("lifecycle nonowner admin", group_ids=[GROUP_ID_ADMIN])
    assert user.is_admin and not user.is_owner
    async with native_http(h) as client:
        form, flow, auth = await open_http(client, h, e, user, kind)
        assert form["type"] == "form" and not form["errors"]
        if operation == "save_error" and kind == "recipe":
            response = await client.post(
                BASE + "/" + form["flow_id"], json={"action": "new", "recipe_id": ""}, headers=auth
            )
            form = await response.json()
            assert form["step_id"] == "recipe_edit"
        owner = e.runtime_data
        entered = asyncio.Event()
        release = asyncio.Event()
        original = type(n).drain

        async def held_drain(self):
            if self is n:
                entered.set()
                await release.wait()
            return await original(self)

        monkeypatch.setattr(type(n), "drain", held_drain)
        unload = asyncio.create_task(h.config_entries.async_unload(e.entry_id))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            assert e.runtime_data is owner
            assert not owner.active
            assert e.state is ConfigEntryState.UNLOAD_IN_PROGRESS
            options = deepcopy(dict(e.options))
            durable = Path(n.store.path).read_bytes()
            messages = list(sink.messages)
            calls = {key: deepcopy(h.data[key]["calls"]) for key in ("p2_fixture", "p3_fixture")}
            projections = projection_spies(monkeypatch, e, n)
            if operation == "cached_get":
                response = await client.get(BASE + "/" + form["flow_id"], headers=auth)
            else:
                payload = {
                    field["name"]: field["default"]
                    for field in form["data_schema"]
                    if "default" in field
                }
                payload["action"] = "save"
                if kind == "recipe":
                    payload["name"] = "PRIVATE LIFECYCLE DRAFT"
                response = await client.post(
                    BASE + "/" + form["flow_id"], json=payload, headers=auth
                )
            body = await response.json()
            record = {
                "kind": kind,
                "operation": operation,
                "status": response.status,
                "state": e.state.value,
                "active": owner.active,
                "same_owner": e.runtime_data is owner,
                "response_type": body.get("type"),
                "step": body.get("step_id"),
                "errors": body.get("errors"),
                "schema_fields": [f["name"] for f in body.get("data_schema", [])],
                "private_cache_retained": getattr(
                    flow, "_quality_dto" if kind == "quality" else "_recipe_dto", None
                )
                is not None,
                "retired": getattr(flow, "_options_retired", None),
                "options_unchanged": dict(e.options) == options,
                "provider_unchanged": sink.messages == messages,
            }
            (tmp_path / (kind + "-" + operation + ".json")).write_text(
                json.dumps(record, indent=2), encoding="utf-8"
            )
            print(json.dumps(record))
            assert response.status == 200
            assert body["type"] == "abort" and body["reason"] == "entry_not_loaded", (
                "private form survived actual native unload in progress"
            )
            assert "data_schema" not in body and not projections
            private_cleared(flow)
            assert flow._options_retired == "entry_not_loaded"
            assert form["flow_id"] not in h.config_entries.options._progress
            with pytest.raises(UnknownFlow):
                await h.config_entries.options.async_configure(form["flow_id"], {})
            again = await getattr(
                flow, "async_step_" + ("quality" if kind == "quality" else "recipes")
            )()
            assert again["type"] == "abort" and again["reason"] == "entry_not_loaded"
            private_cleared(flow)
            assert dict(e.options) == options and Path(n.store.path).read_bytes() == durable
            assert sink.messages == messages
            assert all(h.data[key]["calls"] == calls[key] for key in calls)
        finally:
            release.set()
            assert await asyncio.wait_for(unload, 5)
            assert e.state is ConfigEntryState.NOT_LOADED
            assert not hasattr(e, "runtime_data")


async def test_initial_http_options_after_native_unload(dosing_hass, monkeypatch):
    """An initially unloaded entry is distinct from an admitted private flow."""
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    user = await h.auth.async_create_user("initial lifecycle admin", group_ids=[GROUP_ID_ADMIN])
    assert await h.config_entries.async_unload(e.entry_id)
    await h.async_block_till_done()
    assert e.state is ConfigEntryState.NOT_LOADED and not hasattr(e, "runtime_data")
    options = deepcopy(dict(e.options))
    durable = Path(n.store.path).read_bytes()
    calls = {key: deepcopy(h.data[key]["calls"]) for key in ("p2_fixture", "p3_fixture")}
    messages = list(sink.messages)
    async with native_http(h) as client:
        response = await client.post(
            BASE, json={"handler": e.entry_id}, headers=await headers(h, user)
        )
        body = await response.json()
        assert response.status == 200
        assert body["type"] == "abort" and body["reason"] == "entry_not_loaded"
        assert "data_schema" not in body
    assert dict(e.options) == options and Path(n.store.path).read_bytes() == durable
    assert sink.messages == messages
    assert all(h.data[key]["calls"] == calls[key] for key in calls)
