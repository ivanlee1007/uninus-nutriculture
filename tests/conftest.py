import shutil
from pathlib import Path

import pytest_asyncio
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant

pytest_plugins = ["p2_fixtures"]

DOMAIN = "uninus_nutriculture"


async def make_hass(directory):
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        Path(__file__).resolve().parents[1] / "custom_components",
        directory / "custom_components",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    hass = HomeAssistant(str(directory))
    hass.config.skip_pip = True
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    from homeassistant.bootstrap import async_load_base_functionality

    assert await async_load_base_functionality(hass)
    return hass


def entry(name="Tank", options=None):
    return ConfigEntry(
        domain=DOMAIN,
        title=name,
        data={
            "name": name,
            "ph": "sensor.ph",
            "ec": "sensor.ec",
            "level": "sensor.level",
            "max_age_seconds": 300,
        },
        options=options or {},
        source="user",
        version=1,
        minor_version=1,
        unique_id=None,
        discovery_keys={},
        subentries_data=[],
    )


@pytest_asyncio.fixture
async def hass(tmp_path):
    from homeassistant.const import EVENT_CALL_SERVICE
    from homeassistant.core import callback

    instance = await make_hass(tmp_path / "ha")
    forbidden = []

    @callback
    def observe(event):
        if event.data["domain"] != "number":
            forbidden.append(dict(event.data))

    unsubscribe = instance.bus.async_listen(EVENT_CALL_SERVICE, observe)
    for key, value, unit in (("ph", 5.6, "pH"), ("ec", 0.85, "mS/cm"), ("level", 2.3, "m")):
        instance.states.async_set("sensor." + key, value, {"unit_of_measurement": unit})
    yield instance
    await instance.async_stop(force=True)
    unsubscribe()
    assert not forbidden, f"Forbidden service dispatch: {forbidden}"
