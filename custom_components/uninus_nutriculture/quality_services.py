"""Authenticated management boundary; final admission through commit has no await."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .quality_settings import MAX_REVISION, read, revision, validate
from .recipes import authorize


async def execute(hass, context, service, data):
    await authorize(hass, context)
    e = hass.config_entries.async_get_entry(data["config_entry_id"])
    if e is None or e.domain != DOMAIN or e.state is not ConfigEntryState.LOADED or e.disabled_by:
        raise ServiceValidationError("entry_not_loaded")
    tank = getattr(e, "runtime_data", None)
    if tank is None or not tank.active:
        raise ServiceValidationError("entry_not_loaded")
    async with tank.lock:
        await authorize(hass, context)
        if (
            e.domain != DOMAIN
            or e.state is not ConfigEntryState.LOADED
            or e.disabled_by
            or e.runtime_data is not tank
            or not tank.active
            or hass.config_entries.async_get_entry(e.entry_id) is not e
        ):
            raise ServiceValidationError("entry_not_loaded")
        if service == "save_quality_policy_v1":
            if e.options.get("control_contract_version") != 5:
                raise ServiceValidationError("settings_schema_mismatch")
            previous, rev = read(tank)
            expected = {
                "expected_policy_revision": rev,
                "expected_settings_revision": e.options.get("settings_revision", 0),
                "expected_flow_plan_revision": e.options.get("flow_plan_revision", 0),
            }
            if (
                any(not revision(data.get(k)) or data[k] != v for k, v in expected.items())
                or rev == MAX_REVISION
            ):
                raise ServiceValidationError("quality_conflict")
            policy = validate(data["policy"])
            tank.quality.invalidate("policy_changed")
            if previous["sources"] != policy["sources"]:
                from uuid import uuid4

                tank.quality.tokens.clear()
                tank.quality.samples.clear()
                tank.quality.used.clear()
                tank.quality.regressed.clear()
                tank.quality.epoch = uuid4().hex
            hass.config_entries.async_update_entry(
                e,
                options={
                    **e.options,
                    "quality_policy": dict(schema_version=1, revision=rev + 1, **policy),
                },
            )
            tank.publish()
        return tank.quality.dto()


def register(hass):
    async def handler(call):
        result = await execute(hass, call.context, call.service, call.data)
        return result if call.return_response else None

    fields = {vol.Required("config_entry_id"): vol.All(str, vol.Length(min=1, max=128))}
    for name in ("get_quality_v1", "save_quality_policy_v1"):
        shape = dict(fields)
        if name.startswith("save"):
            shape.update(
                {
                    vol.Required(k): object
                    for k in (
                        "expected_policy_revision",
                        "expected_settings_revision",
                        "expected_flow_plan_revision",
                        "policy",
                    )
                }
            )
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=vol.Schema(shape),
            supports_response=SupportsResponse.ONLY
            if name.startswith("get")
            else SupportsResponse.OPTIONAL,
        )
