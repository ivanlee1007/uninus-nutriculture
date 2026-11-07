"""Additive cache-only result response service."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .control_auth import authorize


def register(hass):
    async def handler(call):
        await authorize(hass, call.context)
        e = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if (
            e is None
            or e.domain != DOMAIN
            or e.state is not ConfigEntryState.LOADED
            or e.disabled_by
        ):
            raise ServiceValidationError("entry_not_loaded")
        tank = getattr(e, "runtime_data", None)
        if tank is None or not tank.active:
            raise ServiceValidationError("entry_not_loaded")
        return tank.results.dto()

    hass.services.async_register(
        DOMAIN,
        "get_result_v1",
        handler,
        schema=vol.Schema(
            {vol.Required("config_entry_id"): vol.All(str, vol.Length(min=1, max=128))}
        ),
        supports_response=SupportsResponse.ONLY,
    )
