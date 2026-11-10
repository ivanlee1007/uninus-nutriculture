"""Authenticated loopback HTTP through Core's registered, decorated Options views."""

from contextlib import asynccontextmanager

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.config.config_entries import (
    OptionManagerFlowIndexView,
    OptionManagerFlowResourceView,
)
from homeassistant.components.http.auth import async_setup_auth
from homeassistant.components.http.request_context import setup_request_context
from homeassistant.helpers.http import KEY_HASS, current_request
from test_p3_dosing import dosing_hass as dosing_hass
from test_p4c_completion import sink_runtime

BASE = "/api/config/config_entries/options/flow"


@asynccontextmanager
async def native_http(h):
    app = web.Application()
    app[KEY_HASS] = h
    setup_request_context(app, current_request)
    await async_setup_auth(h, app)
    for cls in (OptionManagerFlowIndexView, OptionManagerFlowResourceView):
        cls(h.config_entries.options).register(h, app, app.router)
    async with TestClient(TestServer(app, host="127.0.0.1")) as client:
        yield client


async def headers(h, user):
    refresh = await h.auth.async_create_refresh_token(
        user, client_id=None if user.system_generated else "https://native-options.test"
    )
    return {"Authorization": "Bearer " + h.auth.async_create_access_token(refresh)}


async def open_http(client, h, e, user, kind):
    auth = await headers(h, user)
    response = await client.post(BASE, json={"handler": e.entry_id}, headers=auth)
    assert response.status == 200, await response.text()
    f = await response.json()
    assert f["type"] == "form" and f["step_id"] == "init"
    flow = h.config_entries.options._progress[f["flow_id"]]
    assert "user_id" not in flow.context  # Core does not propagate the principal here.
    response = await client.post(
        BASE + "/" + f["flow_id"],
        json={
            **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            kind + "_management": True,
        },
        headers=auth,
    )
    assert response.status == 200, await response.text()
    return await response.json(), flow, auth


@pytest.mark.parametrize(
    "kind,step", [("quality", "quality"), ("recipe", "recipes"), ("notification", "notifications")]
)
async def test_native_http_human_principal_init_navigation_submit(
    dosing_hass, monkeypatch, kind, step
):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    user = await h.auth.async_create_user("HTTP human admin", group_ids=[GROUP_ID_ADMIN])
    from custom_components.uninus_nutriculture.config_flow import NutricultureOptionsFlow

    observed = []
    original = NutricultureOptionsFlow.async_step_init

    async def observe(flow, user_input=None):
        request = current_request.get()
        observed.append((request.method, request["ha_authenticated"], request["hass_user"].id))
        return await original(flow, user_input)

    monkeypatch.setattr(NutricultureOptionsFlow, "async_step_init", observe)
    async with native_http(h) as client:
        f, flow, auth = await open_http(client, h, e, user, kind)
        assert observed == [("POST", True, user.id), ("POST", True, user.id)]
        print("Core request principal reached init/navigation; flow.context=", flow.context)
        assert f["type"] == "form" and f["step_id"] == step and not f["errors"], f
        response = await client.get(BASE + "/" + f["flow_id"], headers=auth)
        assert response.status == 200
        assert (await response.json())["step_id"] == step
        payload = {
            field["name"]: field["default"] for field in f["data_schema"] if "default" in field
        }
        payload["action"] = "cancel"
        response = await client.post(BASE + "/" + f["flow_id"], json=payload, headers=auth)
        assert response.status == 200
        assert (await response.json())["type"] == "abort"
    assert not sink.messages
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
