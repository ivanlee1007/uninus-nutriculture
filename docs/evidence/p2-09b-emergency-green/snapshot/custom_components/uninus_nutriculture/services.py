"""Domain control service admission."""
import voluptuous as vol
from homeassistant.core import SupportsResponse
from .const import DOMAIN


async def async_setup(hass, config):
    async def start(call):
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN or not getattr(entry, "runtime_data", None) or not entry.runtime_data.active:
            from homeassistant.exceptions import ServiceValidationError
            raise ServiceValidationError("entry_not_loaded")
        await entry.runtime_data.control.start(call.context)
        return {"accepted": True, "run_id": entry.runtime_data.control.run_id} if call.return_response else None
    hass.services.async_register(DOMAIN, "start_flow", start,
        schema=vol.Schema({vol.Required("config_entry_id"): str, vol.Optional("request_id"): str}),
        supports_response=SupportsResponse.OPTIONAL)
    return True
