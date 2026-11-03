"""Domain control service admission."""
import voluptuous as vol
from homeassistant.core import SupportsResponse
from .const import DOMAIN


async def async_setup(hass, config):
    async def start(call):
        return {"accepted": False}
    hass.services.async_register(DOMAIN, "start_flow", start,
        schema=vol.Schema({vol.Required("config_entry_id"): str, vol.Optional("request_id"): str}),
        supports_response=SupportsResponse.OPTIONAL)
    return True
