"""Private WebSocket + Options shared notification boundary, never call_service."""

import re

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized

from .const import DOMAIN
from .notifications import MAX, integer, text, validate_policy
from .recipes import authorize

PREFIX = DOMAIN + "/notification_v1/"


async def human(hass, context):
    if context is None or not text(context.user_id):
        raise Unauthorized()
    await authorize(hass, context)


async def execute(hass, context, operation, data):
    await human(hass, context)  # Initial denial precedes entry/target lookup.
    ident = data.get("config_entry_id")
    if not text(ident):
        raise ServiceValidationError("entry_not_loaded")
    e = hass.config_entries.async_get_entry(ident)
    tank = getattr(e, "runtime_data", None) if e else None
    n = getattr(tank, "notifications", None)

    def check():
        if (
            e is None
            or e.domain != DOMAIN
            or e.state is not ConfigEntryState.LOADED
            or e.disabled_by
            or hass.config_entries.async_get_entry(ident) is not e
            or e.runtime_data is not tank
            or n is None
            or not n.live()
        ):
            raise ServiceValidationError("entry_not_loaded")
        if e.options.get("control_contract_version") != 5:
            raise ServiceValidationError("settings_schema_mismatch")

    async def fence():
        await human(hass, context)
        check()

    check()
    if operation == "get":
        return n.dto()
    expected = data.get("expected_epoch")
    async with n.lock:
        await fence()
        if (
            type(expected) is not str
            or re.fullmatch("[0-9a-f]{32}", expected) is None
            or expected != n.epoch
        ):
            raise ServiceValidationError("notification_conflict")
        if operation == "save":
            revision = data.get("expected_revision")
            if not integer(revision) or revision != n.revision or revision == MAX:
                raise ServiceValidationError("notification_conflict")
            if n.indeterminate:
                raise ServiceValidationError("indeterminate")
            p = validate_policy(data.get("policy"))
            if p["provider"] == "notify_entity":
                from .notification_provider import binding

                bound = binding(hass, p["target_entity_id"])
            else:
                bound = None
            p.pop("target_entity_id")
            p["target_binding"] = bound
            check()
            try:
                await n.save(p, fence)
            except ServiceValidationError, Unauthorized:
                raise
            except Exception:
                raise ServiceValidationError("indeterminate") from None
        elif operation == "reconcile":
            try:
                await n.reconcile(fence)
            except ServiceValidationError, Unauthorized:
                raise
            except Exception:
                raise ServiceValidationError("indeterminate") from None
        elif operation == "ack":
            record = next((r for r in n.deliveries if r["event_id"] == data.get("event_id")), None)
            if record is None:
                raise ServiceValidationError("notification_not_found")
            record["acknowledged"] = True
        else:
            raise ServiceValidationError("invalid_notification_policy")
        check()
        if operation in ("save", "reconcile"):
            n.refresh_catalog()
        return n.dto()


def register(hass):
    for op in ("get", "save", "ack", "reconcile"):

        def make(operation):
            @websocket_api.require_admin
            @websocket_api.async_response
            async def handle(hass, connection, msg):
                try:
                    dto = await execute(hass, Context(user_id=connection.user.id), operation, msg)
                    connection.send_result(msg["id"], dto)
                except Unauthorized:
                    connection.send_error(msg["id"], "unauthorized", "unauthorized")
                except ServiceValidationError as err:
                    code = str(err)
                    allowed = {
                        "entry_not_loaded",
                        "settings_schema_mismatch",
                        "invalid_notification_policy",
                        "invalid_provider",
                        "notification_conflict",
                        "notification_not_found",
                        "storage_failed",
                        "indeterminate",
                    }
                    code = code if code in allowed else "invalid_notification_policy"
                    connection.send_error(msg["id"], code, code)

            return handle

        fields = {
            vol.Required("id"): vol.All(
                lambda v: v if type(v) is int else (_ for _ in ()).throw(vol.Invalid("invalid id")),
                vol.Range(min=1, max=MAX),
            ),
            vol.Required("type"): PREFIX + op,
            vol.Required("config_entry_id"): object,
        }
        if op != "get":
            fields[vol.Required("expected_epoch")] = object
        if op == "save":
            fields.update(
                {vol.Required("expected_revision"): object, vol.Required("policy"): object}
            )
        if op == "ack":
            fields[vol.Required("event_id")] = object
        websocket_api.async_register_command(hass, PREFIX + op, make(op), vol.Schema(fields))
