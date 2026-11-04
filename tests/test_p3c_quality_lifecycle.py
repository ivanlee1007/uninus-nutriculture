"""Native runtime regressions for selected-source health and closed-run renewal."""

import asyncio
import time
from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import plan, prepared, save_v5, until


@pytest.mark.parametrize(
    "key,damage",
    [
        ("ph", "lost"),
        ("ec", "unit"),
        ("ph", "restored"),
        ("ec", "finite"),
        ("ph", "stale"),
        ("ec", "threshold"),
    ],
)
async def test_selected_mix_source_health(dosing_hass, key, damage):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    p["rows"][1].update(
        start_rule="flow_start",
        delay_seconds=0,
        condition=dict(source=key, operator="gte", value=6 if key == "ph" else 0.65),
    )
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    c = entry.runtime_data.control
    circ = hass.data["p3_fixture"]["outputs"][1]
    await start_native(hass, entry)
    try:
        await until(lambda: c.mix_stage.circulation_confirmed)
        entity = "sensor." + key
        unit = "pH" if key == "ph" else "mS/cm"
        if damage in ("lost", "restored"):
            hass.states.async_set(entity, "unavailable")
            if damage == "restored":
                hass.states.async_set(entity, "6.5", {"unit_of_measurement": unit})
        elif damage == "unit":
            hass.states.async_set(entity, ".7", {"unit_of_measurement": "wrong"})
        elif damage == "finite":
            hass.states.async_set(entity, "nan", {"unit_of_measurement": unit})
        elif damage == "stale":
            # Explicit state-age seam, not physical-circulation clock acceleration.
            hass.states.get(entity).last_reported = dt_util.utcnow() - timedelta(seconds=301)
        else:
            # A healthy value outside admission condition is NOT continuous control.
            hass.states.async_set(entity, ".6", {"unit_of_measurement": unit})
        await asyncio.sleep(0.2)
        if damage == "threshold":
            assert c.fault is None and c.running and circ.is_on
        else:
            await until(lambda: not c.running)
            assert c.fault == "source_invalid"
            assert not circ.is_on and not c.leases
            assert c.flow.records["mix"]["result"] == "fault"
            assert c.flow.records["acid"]["started_at"] is None
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_mix_two_closed_runs_new_physical_deadline(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    p["rows"][1].update(start_rule="flow_start", delay_seconds=0)
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    c = entry.runtime_data.control
    stage = c.mix_stage
    circ = hass.data["p3_fixture"]["outputs"][1]
    first = await start_native(hass, entry)
    try:
        await until(lambda: stage.circulation_confirmed)
        oldcutoff = stage.circ_physical_cutoff
        # Accelerate only standalone logical mix completion, not physical session time.
        stage.clock = lambda: stage.end + 1
        stage.wake.set()
        await until(lambda: not c.running)
        assert c.fault is None and c.flow.records["mix"]["result"] == "completed"
        assert not circ.is_on and not c.leases
        assert c.flow.circ_start is None and c.flow.circ_cutoff is None
        stage.clock = time.monotonic
        # Explicit stale-field seam ONLY for this mix adjacent comparison.
        # Original nutrient probe independently retains the real C-F wait.
        stage.circ_physical_cutoff = time.monotonic() - 0.1
        second = await start_native(hass, entry)
        await until(lambda: circ.is_on or c.fault is not None)
        assert first["run_id"] != second["run_id"]
        assert c.fault is None and circ.is_on
        assert stage.circ_physical_cutoff > oldcutoff
    finally:
        stage.clock = time.monotonic
        await toggle(hass, entry, "flow_run", False)


async def test_nutrient_real_expiry_then_new_run(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    ui = await hass.config_entries.options.async_init(entry.entry_id)
    values = {
        **dict(entry.options["dosing_parameters"]),
        "ph": "sensor.ph",
        "ec": "sensor.ec",
        "level": "sensor.level",
        "max_age_seconds": 300,
        "mix_commissioned": False,
        "circulation_device_max_on_seconds": 6,
    }
    saved = await hass.config_entries.options.async_configure(ui["flow_id"], values)
    assert saved["type"] == "create_entry", saved
    assert entry.options["control"]["circulation_device_max_on_seconds"] == 6
    p = plan()
    for i, row in enumerate(p["rows"]):
        row.update(
            stage=("nutrient", "refill", "acid", "mix")[i],
            start_rule="flow_start" if i == 0 else "after_previous_finished",
            delay_seconds=0,
        )
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "nutrient_enabled")
    c = entry.runtime_data.control
    pump, circ = hass.data["p3_fixture"]["outputs"]
    first = await start_native(hass, entry)
    try:
        await until(lambda: pump.is_on)
        hass.states.async_set("sensor.ec", ".86", {"unit_of_measurement": "mS/cm"})
        await until(lambda: c.nutrient_stage.phase == "waiting_sample")
        hass.states.async_set("sensor.ec", ".87", {"unit_of_measurement": "mS/cm"})
        await until(lambda: not c.running)
        assert c.flow.records["nutrient"]["result"] == "completed" and c.fault is None
        assert not pump.is_on and not circ.is_on and not c.leases
        assert c.flow.circ_start is None and c.flow.circ_cutoff is None
        oldcutoff = c.nutrient_stage.circ_physical_cutoff
        await asyncio.sleep(max(0, oldcutoff - time.monotonic()) + 0.1)
        hass.states.async_set("sensor.ec", ".7", {"unit_of_measurement": "mS/cm"})
        pump.entered_on.clear()
        second = await start_native(hass, entry)
        await until(lambda: pump.is_on or c.fault is not None)
        assert c.fault is None and pump.is_on
        assert first["run_id"] != second["run_id"]
        assert c.nutrient_stage.circ_physical_cutoff > oldcutoff
        assert c.flow.circ_start > oldcutoff
    finally:
        await toggle(hass, entry, "flow_run", False)
