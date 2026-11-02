from pathlib import Path
import shutil
import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.helpers import frame, entity_registry, device_registry

DOMAIN = "uninus_nutriculture"

async def make_hass(directory):
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(__file__).resolve().parents[1] / "custom_components", directory / "custom_components", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    hass = HomeAssistant(str(directory))
    hass.config.skip_pip = True
    loader.async_setup(hass)
    frame.async_setup(hass)
    await entity_registry.async_load(hass)
    await device_registry.async_load(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    return hass

def entry(name="Tank", options=None):
    return ConfigEntry(domain=DOMAIN, title=name, data={"name":name,"ph":"sensor.ph","ec":"sensor.ec","level":"sensor.level","max_age_seconds":300}, options=options or {}, source="user", version=1, minor_version=1, unique_id=None, discovery_keys={}, subentries_data=[])

@pytest_asyncio.fixture
async def hass(tmp_path):
    instance = await make_hass(tmp_path / "ha")
    for key, value, unit in (("ph",5.6,"pH"),("ec",0.85,"mS/cm"),("level",2.3,"m")):
        instance.states.async_set("sensor."+key, value, {"unit_of_measurement":unit})
    yield instance
    await instance.async_stop(force=True)
