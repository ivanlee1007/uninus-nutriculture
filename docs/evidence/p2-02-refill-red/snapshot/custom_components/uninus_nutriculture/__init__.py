"""UNiNUS Nutriculture: read-only shadow observation, never actuation."""

from homeassistant.const import Platform

from .manager import Tank


async def async_setup_entry(hass, entry):
    entry.runtime_data = Tank(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.NUMBER])
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR, Platform.SWITCH])
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass, entry):
    if entry.runtime_data.binding != entry.runtime_data.sources:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    entry.runtime_data.active = False
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform.NUMBER, Platform.SENSOR]
    )
    if not unloaded:
        entry.runtime_data.active = True
    return unloaded
