"""P4b actual registered Core management entry tracer."""

from copy import deepcopy

from homeassistant.auth import auth_manager_from_config
from homeassistant.core import Context
from homeassistant.helpers import entity_registry as er
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3c_flow import prepared, save_v5

DOMAIN = "uninus_nutriculture"


async def owner(hass):
    hass.auth = await auth_manager_from_config(hass, [], [])
    user = await hass.auth.async_create_user("owner")
    return Context(user_id=user.id)


async def api(hass, context, entry, service="get_quality_v1", **data):
    return await hass.services.async_call(
        DOMAIN,
        service,
        {"config_entry_id": entry.entry_id, **data},
        blocking=True,
        return_response=True,
        context=context,
    )


async def test_registered_quality_service(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    assert h.services.has_service(DOMAIN, "get_quality_v1"), (
        "quality read transport is not registered"
    )
    dto = await api(h, await owner(h), e)
    assert dto["policy_revision"] == 0 and dto["permit"]["granted"] is False
    assert "quality_policy" not in e.options


async def test_native_quality_editor_save_readback_cancel_zero_actuation(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    ctx = await owner(h)
    before = deepcopy(dict(e.options))
    f = await h.config_entries.options.async_init(e.entry_id, context={"user_id": ctx.user_id})
    fields = {str(k) for k in f["data_schema"].schema}
    assert "quality_management" in fields, "native quality editor is missing"
    f = await h.config_entries.options.async_configure(
        f["flow_id"],
        {
            **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            "quality_management": True,
        },
    )
    assert f["step_id"] == "quality"
    assert dict(e.options) == before
    values = {
        str(k): k.default()
        for k in f["data_schema"].schema
        if k.default is not __import__("voluptuous").UNDEFINED
    }
    values.update(
        stable_samples=2,
        stable_interval_seconds=1,
        stable_duration_seconds=2,
        permit_ttl_seconds=3,
        action="save",
    )
    f = await h.config_entries.options.async_configure(f["flow_id"], values)
    assert e.options.get("quality_policy", {}).get("revision") == 1
    assert f["type"] == "abort"
    dto = await api(h, ctx, e)
    assert dto["policy"]["stable_duration_seconds"] == 2
    saved = deepcopy(dict(e.options))
    f = await h.config_entries.options.async_init(e.entry_id, context={"user_id": ctx.user_id})
    f = await h.config_entries.options.async_configure(
        f["flow_id"],
        {
            **{k: e.data[k] for k in ("ph", "ec", "level", "max_age_seconds")},
            "quality_management": True,
        },
    )
    f = await h.config_entries.options.async_configure(
        f["flow_id"], {**values, "action": "cancel", "permit_ttl_seconds": 9}
    )
    assert f["type"] == "abort" and dict(e.options) == saved
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]


async def test_native_quality_entities_registered_readonly(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    rows = er.async_entries_for_config_entry(er.async_get(h), e.entry_id)
    actual = {r.unique_id: r for r in rows}
    assert f"{e.entry_id}:quality_status" in actual, "native quality status absent"
    assert f"{e.entry_id}:irrigation_permit" in actual, "readonly permit absent"
    row = actual[f"{e.entry_id}:irrigation_permit"]
    assert row.domain == "binary_sensor"
    assert h.states.get(row.entity_id).state == "off"
