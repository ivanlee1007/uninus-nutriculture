"""UNiNUS Nutriculture: read-only shadow observation, never actuation."""
from homeassistant.const import Platform
from .manager import Tank

async def async_setup_entry(hass, entry):
    entry.runtime_data = Tank(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.NUMBER])
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True

async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.NUMBER, Platform.SENSOR])
