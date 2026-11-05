# ruff: noqa: E402
import asyncio
import json
import sys
from pathlib import Path

import homeassistant  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from conftest import make_hass


async def main():
    h = await make_hass(Path(sys.argv[1]))
    try:
        e = h.config_entries.async_entries("uninus_nutriculture")
        assert len(e) == 1
        e = e[0]
        before = dict(e.options)
        # Recreate only isolated hardware telemetry before canonical startup.
        from homeassistant.helpers import entity_registry as er

        hardware = []
        for row in er.async_get(h).entities.values():
            if row.entity_id.startswith("switch.") and row.platform == "switch":
                h.states.async_set(row.entity_id, "off")
                hardware.append(row.entity_id)
        for key, value, unit in [("ph", 5.6, "pH"), ("ec", 0.85, "mS/cm"), ("level", 2, "m")]:
            h.states.async_set("sensor." + key, value, {"unit_of_measurement": unit})
        assert hardware
        assert await h.config_entries.async_setup(e.entry_id)
        await h.async_block_till_done()
        if dict(e.options) != before:
            print(
                json.dumps(
                    {
                        "readback_setup_options_delta": {
                            k: {"before": before.get(k), "after": e.options.get(k)}
                            for k in set(before) | set(e.options)
                            if before.get(k) != e.options.get(k)
                        },
                        "before": before,
                        "after": dict(e.options),
                    }
                ),
                flush=True,
            )
        assert dict(e.options) == before
        from test_p2_control import target

        p = dict(e.runtime_data.parameters)
        numbers = {k: float(h.states.get(target(h, e, "number", k)).state) for k in p}
        assert numbers == p
        status = h.states.get(target(h, e, "sensor", "control_status"))
        assert status.attributes["parameters"] == p
        print(
            json.dumps(
                {
                    "options": dict(e.options),
                    "effective_parameters": numbers,
                    "status_parameters": dict(status.attributes["parameters"]),
                    "entry_state": e.state.value,
                    "pid": __import__("os").getpid(),
                }
            )
        )
    finally:
        await h.async_stop(force=True)


asyncio.run(main())
