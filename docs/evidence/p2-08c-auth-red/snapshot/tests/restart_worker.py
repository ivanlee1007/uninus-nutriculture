"""Fresh-process native Core/storage probe. No HTTP listener or live HA."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conftest import DOMAIN, entry, make_hass
from homeassistant.const import __version__
from homeassistant.helpers import entity_registry as er
from test_writes import change, ids

EXPECTED = {
    "level_low": 2.2,
    "level_high": 2.5,
    "ph_low": 5.5,
    "ph_high": 5.9,
    "ec_low": 0.81,
    "ec_high": 0.95,
    "refill_timeout": 191,
    "ec_timeout": 91,
    "ph_timeout": 191,
    "mix_duration": 11,
}


async def main():
    hass = await make_hass(Path(sys.argv[2]))
    try:
        for key, value, unit in [("ph", 5.6, "pH"), ("ec", 0.85, "mS/cm"), ("level", 2.3, "m")]:
            hass.states.async_set("sensor." + key, value, {"unit_of_measurement": unit})
        if sys.argv[1] == "write":
            tank = entry()
            await hass.config_entries.async_add(tank)
            await hass.async_block_till_done()
            entities = ids(hass, tank)
            for key, value in EXPECTED.items():
                await change(hass, entities[key], value)
            er.async_get(hass).async_update_entity(
                entities["ph_low"], new_entity_id="number.persisted_ph_limit"
            )
            await hass.async_block_till_done()
        else:
            entries = hass.config_entries.async_entries(DOMAIN)
            assert len(entries) == 1
            tank = entries[0]
            assert await hass.config_entries.async_setup(tank.entry_id)
            await hass.async_block_till_done()
        entities = ids(hass, tank)
        actual = {key: float(hass.states.get(entities[key]).state) for key in EXPECTED}
        assert actual == EXPECTED
        assert entities["ph_low"] == "number.persisted_ph_limit"
        status = hass.states.get(entities["status"])
        assert status.state == "within_range"
        assert status.attributes["ready_for_irrigation"] is False
        assert dict(status.attributes["parameters"]) == EXPECTED
        print(
            json.dumps(
                {
                    "version": __version__,
                    "entry_id": tank.entry_id,
                    "entities": entities,
                    "parameters": actual,
                }
            )
        )
        assert await hass.config_entries.async_unload(tank.entry_id)
    finally:
        # Native final-write flush; explicitly NOT a crash/power-loss test.
        await hass.async_stop(force=True)


asyncio.run(main())
