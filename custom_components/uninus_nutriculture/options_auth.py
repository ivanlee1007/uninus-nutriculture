"""Bind native Options to the server-verified human, never a submitted identity."""

from functools import wraps

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers.http import (
    KEY_AUTHENTICATED,
    KEY_HASS,
    HomeAssistantView,
    current_request,
)

from .recipes import authorize


def options_context(flow):
    """Resolve each HTTP request afresh; retain trusted manager-only compatibility."""
    request = current_request.get()
    if request is not None:
        if request.get(KEY_AUTHENTICATED) is not True or request.app.get(KEY_HASS) is not flow.hass:
            raise Unauthorized()
        context = HomeAssistantView.context(request)
        claimed = flow.context.get("user_id")
        if claimed is not None and claimed != context.user_id:
            raise Unauthorized()
    else:
        if getattr(flow, "_options_http", False):
            raise Unauthorized()
        context = Context(user_id=flow.context.get("user_id"))
    if hasattr(flow, "_options_principal") and context.user_id != flow._options_principal:
        raise Unauthorized()
    return context


async def check_options(flow):
    """Recheck live authority before private reads and after awaited work."""
    if reason := getattr(flow, "_options_retired", None):
        raise ServiceValidationError(reason)
    context = options_context(flow)
    await authorize(flow.hass, context)
    owner = getattr(flow.config_entry, "runtime_data", None)
    if (
        flow.config_entry.state is not ConfigEntryState.LOADED
        or owner is None
        or not getattr(owner, "active", False)
        or (hasattr(flow, "_options_owner") and owner is not flow._options_owner)
    ):
        raise ServiceValidationError("entry_not_loaded")
    flow._options_principal = context.user_id
    flow._options_http = current_request.get() is not None
    flow._options_owner = owner


def retire_options(flow, reason):
    """A restored role must start a fresh flow, not resurrect a private draft."""
    for key in (
        "_quality_dto",
        "_recipe_dto",
        "_recipe_draft",
        "_recipe_identity",
        "_notification_dto",
        "_notification_owner",
        "_options_owner",
    ):
        setattr(flow, key, None)
    flow._notification_fields = set()
    flow._notification_retired = reason
    flow._options_retired = reason
    return flow.async_abort(reason=reason)


def human_options(method):
    """Keep all private native forms behind the same current-human boundary."""

    @wraps(method)
    async def guarded(flow, *args, **kwargs):
        try:
            await check_options(flow)
            result = await method(flow, *args, **kwargs)
            await check_options(flow)
            return result
        except Unauthorized:
            return retire_options(flow, "unauthorized")
        except ServiceValidationError as err:
            if str(err) in ("entry_not_loaded", "unauthorized"):
                return retire_options(flow, str(err))
            raise

    return guarded


def native_options(method):
    """Bind the HTTP init form before navigation, without changing internal setup."""
    guarded = human_options(method)

    @wraps(method)
    async def native(flow, *args, **kwargs):
        if current_request.get() is not None or getattr(flow, "_options_http", False):
            return await guarded(flow, *args, **kwargs)
        return await method(flow, *args, **kwargs)

    return native
