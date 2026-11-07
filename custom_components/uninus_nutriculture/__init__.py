"""Passive monitoring plus explicitly commissioned P2 refill control."""

from homeassistant.const import Platform

from .manager import Tank
from .services import async_setup  # noqa: F401


async def async_setup_entry(hass, entry):
    from .control import Controller

    entry.runtime_data = Tank(hass, entry)
    entry.runtime_data.control = Controller(entry.runtime_data)
    from .quality import QualityCoordinator

    entry.runtime_data.quality = QualityCoordinator(entry.runtime_data)
    from .results import ResultCoordinator

    entry.runtime_data.results = ResultCoordinator(entry.runtime_data)
    from .notifications import Notifications

    entry.runtime_data.notifications = Notifications(entry.runtime_data)
    await entry.runtime_data.notifications.setup()
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.NUMBER])
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON, Platform.BINARY_SENSOR]
    )
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    # Rebuild the non-persistent provider cache from the loaded policy, not defaults.
    entry.runtime_data.notifications.refresh_catalog()
    return True


async def _options_updated(hass, entry):
    if entry.runtime_data.binding != entry.runtime_data.sources:
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        control = entry.runtime_data.control
        if not control.running and not control.fault:
            if not entry.options.get("control", {}).get("commissioned"):
                control.flow_state = "uncommissioned"
            elif control.flow_state == "uncommissioned":
                control.flow_state = "idle" if control.master else "disabled"
        entry.runtime_data.publish()


async def async_unload_entry(hass, entry):
    entry.runtime_data.notifications.close()
    entry.runtime_data.results.close()
    entry.runtime_data.quality.close()
    if not await entry.runtime_data.control.shutdown():
        return False
    await entry.runtime_data.notifications.drain()
    unloaded = await hass.config_entries.async_unload_platforms(
        entry,
        [
            Platform.NUMBER,
            Platform.SENSOR,
            Platform.SWITCH,
            Platform.BUTTON,
            Platform.BINARY_SENSOR,
        ],
    )
    return unloaded
