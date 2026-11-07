"""Native unload before the first notification Options step must retire safely."""

import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from aiohttp.test_utils import make_mocked_request
from homeassistant.components.config.config_entries import OptionManagerFlowResourceView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import UnknownFlow
from test_p3_dosing import dosing_hass as dosing_hass
from test_p4c_completion import sink_runtime


@pytest.mark.parametrize("route", ["manager", "http_view"])
async def test_initial_notification_options_after_native_unload_retires(dosing_hass, route):
    h = dosing_hass
    e, n, c, replies, sink = await sink_runtime(h)
    assert c.user.is_admin
    initial = await h.config_entries.options.async_init(e.entry_id, context={"user_id": c.user.id})
    assert initial["type"] == "form" and initial["step_id"] == "init"
    flow_id = initial["flow_id"]
    flow = h.config_entries.options._progress[flow_id]
    assert not hasattr(flow, "_notification_owner")
    assert not hasattr(flow, "_notification_dto")
    assert await h.config_entries.async_unload(e.entry_id)
    await h.async_block_till_done()
    assert e.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(e, "runtime_data")  # Core, not a manual delattr, removed it.
    storage = Path(h.config.path(".storage"))

    def durable():
        return {
            str(p.relative_to(storage)): p.read_bytes()
            for p in storage.rglob("*")
            if p.is_file() and "uninus_nutriculture" in p.name
        }

    before = durable()
    assert Path(n.store.path).read_bytes()
    calls = {key: deepcopy(h.data[key]["calls"]) for key in ("p2_fixture", "p3_fixture")}
    options = deepcopy(dict(e.options))
    messages = list(sink.messages)
    payload = {
        **{key: e.data[key] for key in ("ph", "ec", "level", "max_age_seconds")},
        "notification_management": True,
    }
    record = {
        "route": route,
        "native_state": e.state.value,
        "runtime_data_absent": not hasattr(e, "runtime_data"),
        "is_admin": c.user.is_admin,
        "io_baseline_after_native_unload": True,
    }
    try:
        if route == "manager":
            result = await h.config_entries.options.async_configure(flow_id, payload)
        else:
            request = make_mocked_request(
                "POST",
                "/api/config/config_entries/options/flow/" + flow_id,
                headers={"Content-Type": "application/json"},
            )
            request["hass_user"] = c.user
            request._read_bytes = json.dumps(payload).encode()
            response = await OptionManagerFlowResourceView(h.config_entries.options).post(
                request, flow_id
            )
            record["http_status"] = response.status
            assert response.status == 200
            result = json.loads(response.body)
        record["result"] = result
        assert result["type"] == "abort" and result["reason"] == "entry_not_loaded"
        assert "data_schema" not in result
        assert sink.entity_id not in str(result)
        assert n.epoch not in str(result)
        assert flow._notification_dto is None
        assert not flow._notification_fields
        assert flow._notification_owner is None
        assert flow._notification_retired == "entry_not_loaded"
        assert flow_id not in h.config_entries.options._progress
        with pytest.raises(UnknownFlow):
            await h.config_entries.options.async_configure(flow_id, payload)
        again = await flow.async_step_notifications()
        assert again["type"] == "abort" and again["reason"] == "entry_not_loaded"
        assert flow._notification_dto is None and flow._notification_owner is None
    except Exception as err:
        record["exception_type"] = type(err).__name__
        record["exception"] = str(err)
        raise
    finally:
        record["no_durable_write"] = durable() == before
        record["no_actuator_io"] = all(h.data[key]["calls"] == calls[key] for key in calls)
        record["no_provider_io"] = sink.messages == messages
        record["options_unchanged"] = dict(e.options) == options
        if directory := os.environ.get("GATE_OUT"):
            out = Path(directory)
            out.mkdir(parents=True, exist_ok=True)
            (out / ("unloaded-" + route + ".json")).write_text(
                json.dumps(record, indent=2), encoding="utf-8"
            )
    assert all(
        record[key]
        for key in ("no_durable_write", "no_actuator_io", "no_provider_io", "options_unchanged")
    )
