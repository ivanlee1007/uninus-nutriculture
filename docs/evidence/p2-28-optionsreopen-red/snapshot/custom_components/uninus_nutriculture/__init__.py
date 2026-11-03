"""UNiNUS Nutriculture: read-only shadow observation, never actuation."""

from homeassistant.const import Platform

from .manager import Tank
from .services import async_setup  # noqa: F401


async def async_setup_entry(hass, entry):
    from .control import Controller

    entry.runtime_data = Tank(hass, entry)
    entry.runtime_data.control = Controller(entry.runtime_data)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.NUMBER])
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON])
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass, entry):
    if entry.runtime_data.binding != entry.runtime_data.sources:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if not await entry.runtime_data.control.shutdown():
        return False
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH, Platform.BUTTON]
    )
    return unloaded
