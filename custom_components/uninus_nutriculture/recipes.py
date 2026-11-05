"""Entry-owned recipe v1 transactions, with no actuator dispatch."""

from copy import deepcopy
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError, Unauthorized

from .const import DOMAIN
from .manager import validate


async def authorize(hass, context):
    if context is None or context.user_id is None:
        raise Unauthorized()
    user = await hass.auth.async_get_user(context.user_id)
    if user is None or not user.is_active or not user.is_admin or user.system_generated:
        raise Unauthorized()


def catalog(tank):
    return deepcopy(
        tank.entry.options.get(
            "recipe_catalog", dict(schema_version=1, revision=0, recipes=[], last_applied=None)
        )
    )


def dto(tank):
    c = catalog(tank)
    last = c["last_applied"]
    return dict(
        schema_version=1,
        config_entry_id=tank.entry.entry_id,
        catalog_revision=c["revision"],
        settings_revision=tank.entry.options.get("settings_revision", 0),
        recipes=c["recipes"],
        last_applied=last,
        parameters_match=last is not None and last["parameters"] == tank.parameters,
        parameters=dict(tank.parameters),
    )


def revision(value):
    if type(value) is not int or value < 0:
        raise vol.Invalid("invalid_revision")
    return value


def record(name, parameters, identity):
    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 80
        or any(ord(c) < 32 for c in name)
    ):
        raise ServiceValidationError("invalid_recipe")
    if not isinstance(parameters, dict):
        raise ServiceValidationError("invalid_recipe")
    try:
        validate(parameters)
    except ServiceValidationError as err:
        raise ServiceValidationError("invalid_recipe") from err
    return dict(id=identity, name=name.strip(), parameters=dict(parameters))


def transact(tank, service, data):
    c = catalog(tank)
    if service != "get_recipes_v1":
        if data["expected_catalog_revision"] != c["revision"]:
            raise ServiceValidationError("recipe_conflict")
        identity = data["recipe_id"]
        found = next((r for r in c["recipes"] if r["id"] == identity), None)
        if service == "save_recipe_v1":
            if identity is not None and found is None:
                raise ServiceValidationError("recipe_not_found")
            candidate = record(data["name"], data["parameters"], identity or uuid4().hex)
            if candidate == found:
                return dto(tank)
            if found is None:
                if len(c["recipes"]) >= 100:
                    raise ServiceValidationError("recipe_limit")
                c["recipes"].append(candidate)
            else:
                c["recipes"][c["recipes"].index(found)] = candidate
            c["revision"] += 1
            tank.hass.config_entries.async_update_entry(
                tank.entry, options={**tank.entry.options, "recipe_catalog": c}
            )
        elif service == "delete_recipe_v1":
            if data["confirm_delete"] is not True:
                raise ServiceValidationError("confirmation_required")
            if found is None:
                raise ServiceValidationError("recipe_not_found")
            c["recipes"].remove(found)
            c["revision"] += 1
            tank.hass.config_entries.async_update_entry(
                tank.entry, options={**tank.entry.options, "recipe_catalog": c}
            )
        elif service == "apply_recipe_v1":
            if data["expected_settings_revision"] != tank.entry.options.get("settings_revision", 0):
                raise ServiceValidationError("settings_conflict")
            if found is None:
                raise ServiceValidationError("recipe_not_found")
            control = tank.control
            if (
                control.running
                or control.leases
                or control.lock.locked()
                or any(not waiter.done() for waiter in (tank.lock._waiters or ()))
                or any(
                    task is not None and not task.done()
                    for task in (control.on_task, control.off_task)
                )
            ):
                raise ServiceValidationError("busy")
            last = dict(
                recipe_id=found["id"], name=found["name"], parameters=dict(found["parameters"])
            )
            if c["last_applied"] != last:
                c["last_applied"] = last
                c["revision"] += 1
            tank.write_settings(
                parameters=found["parameters"],
                expected_revision=data["expected_settings_revision"],
                _recipe_catalog=c,
                _recipe_application=True,
            )
    return dto(tank)


async def execute(hass, context, service, data):
    await authorize(hass, context)
    entry = hass.config_entries.async_get_entry(data["config_entry_id"])
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
        or entry.disabled_by
    ):
        raise ServiceValidationError("entry_not_loaded")
    tank = getattr(entry, "runtime_data", None)
    if tank is None or not tank.active:
        raise ServiceValidationError("entry_not_loaded")
    async with tank.lock:
        await authorize(hass, context)
        if (
            not tank.active
            or entry.runtime_data is not tank
            or entry.state is not ConfigEntryState.LOADED
            or entry.disabled_by
            or hass.config_entries.async_get_entry(entry.entry_id) is not entry
        ):
            raise ServiceValidationError("entry_not_loaded")
        if entry.options.get("control_contract_version") != 5:
            raise ServiceValidationError("settings_schema_mismatch")
        result = transact(tank, service, data)
    return result


def register(hass):
    async def handle(call):
        result = await execute(hass, call.context, call.service, call.data)
        return result if call.return_response else None

    base = {vol.Required("config_entry_id"): str}
    mutation = {
        **base,
        vol.Required("expected_catalog_revision"): revision,
        vol.Required("recipe_id"): vol.Any(None, str),
    }
    for service, fields in (
        ("get_recipes_v1", base),
        ("delete_recipe_v1", {**mutation, vol.Required("confirm_delete"): object}),
        (
            "save_recipe_v1",
            {**mutation, vol.Required("name"): str, vol.Required("parameters"): dict},
        ),
        ("apply_recipe_v1", {**mutation, vol.Required("expected_settings_revision"): revision}),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            handle,
            schema=vol.Schema(fields),
            supports_response=SupportsResponse.ONLY
            if service == "get_recipes_v1"
            else SupportsResponse.OPTIONAL,
        )
