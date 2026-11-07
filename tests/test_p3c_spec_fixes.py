"""Independent native boundaries, no production monkeypatch or source edits."""

import asyncio
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import DAYS, STAGES, call, plan, prepared, save_v5, until


def capture(name, data):
    if capture_dir := os.environ.get("P3C_CAPTURE_DIR"):
        output = Path(capture_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / (name + ".json")).write_text(json.dumps(data, default=str, indent=2))


async def test_native_options_open_abort_and_plan_form(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    before = deepcopy(dict(entry.options))
    opened = await hass.config_entries.options.async_init(entry.entry_id)
    opened = await hass.config_entries.options.async_configure(
        opened["flow_id"], {"flow_plan": True}
    )
    fields = {str(k.schema): type(v).__name__ for k, v in opened["data_schema"].schema.items()}
    hass.config_entries.options.async_abort(opened["flow_id"])
    capture(
        "options-open",
        dict(
            type=opened["type"],
            step_id=opened["step_id"],
            fields=fields,
            unchanged=dict(entry.options) == before,
            version=entry.options["control_contract_version"],
        ),
    )
    assert dict(entry.options) == before
    assert entry.options["control_contract_version"] == 4
    assert any(
        "start_rule" in k or "flow_plan" in k or "run_timeout_seconds" in k for k in fields
    ), "Native Options has no P3c plan fields/menu at all"


async def test_native_options_v5_weekday_bumps_both_revisions(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    before = deepcopy(dict(entry.options))
    opened = await hass.config_entries.options.async_init(entry.entry_id)
    opened = await hass.config_entries.options.async_configure(
        opened["flow_id"], {"flow_plan": True}
    )
    payload = {}
    for marker, validator in opened["data_schema"].schema.items():
        name = str(marker.schema)
        suggested = (marker.description or {}).get("suggested_value")
        if suggested is not None:
            payload[name] = suggested
        elif name in ("ph", "ec", "level", "max_age_seconds"):
            payload[name] = entry.options.get(name, entry.data.get(name))
    payload["row_1_weekdays"] = ["mon"]
    result = await hass.config_entries.options.async_configure(opened["flow_id"], payload)
    capture(
        "options-weekday",
        dict(
            result_type=result["type"],
            errors=result.get("errors"),
            before_settings=before["settings_revision"],
            after_settings=entry.options["settings_revision"],
            before_plan=before["flow_plan_revision"],
            after_plan=entry.options["flow_plan_revision"],
            days=entry.options["control"]["allowed_weekdays"],
            calls=hass.data["p3_fixture"]["calls"],
        ),
    )
    assert result["type"] == "create_entry", result
    assert entry.options["control"]["allowed_weekdays"]["mix"] == ["mon"]
    assert entry.options["settings_revision"] == before["settings_revision"] + 1
    assert entry.options["flow_plan_revision"] == before["flow_plan_revision"] + 1, (
        "weekday mutation bypassed plan revision"
    )


async def test_unreachable_refill_cannot_justify_low_mix_wait(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    for i, s in enumerate(("mix", "refill", "nutrient", "acid")):
        p["rows"][i].update(
            stage=s,
            start_rule="flow_start"
            if i == 0
            else "after_previous_started"
            if i == 1
            else "after_previous_finished",
            delay_seconds=0,
            wait_timeout_seconds=10,
        )
    await save_v5(hass, entry, p)
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    await toggle(hass, entry, "refill_enabled")
    c = entry.runtime_data.control
    payload = dict(
        config_entry_id=entry.entry_id,
        expected_revision=entry.options["settings_revision"],
        expected_flow_plan_revision=entry.options["flow_plan_revision"],
        flow_plan=p,
        allowed_weekdays={s: list(DAYS) for s in STAGES},
        weekday=DAYS[__import__("homeassistant.util.dt", fromlist=["now"]).now().weekday()],
    )
    preview = await call(hass, "preview_flow_plan_v5", payload)
    await start_native(hass, entry)
    try:
        await until(lambda: c.flow.records["mix"]["phase"] == "waiting_condition" or c.fault)
        await asyncio.sleep(0.12)
        capture(
            "unreachable-refill",
            dict(
                preview=preview,
                records=deepcopy(c.flow.records),
                fault=c.fault,
                running=c.running,
                refill_calls=hass.data["p2_fixture"]["calls"],
                chemical_calls=hass.data["p3_fixture"]["calls"],
            ),
        )
        assert c.fault == "level_unsafe", (
            "Unstarted refill depends on mix.started: it cannot independently improve level; runtime must not wait on it"
        )
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_preview_blocked_dependency_propagates_finished_anchor(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    # refill disabled -> mix after-start blocked -> nutrient after-finish must also block.
    p["rows"][1].update(delay_seconds=0)
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    await toggle(hass, entry, "nutrient_enabled")
    preview = await call(
        hass,
        "preview_flow_plan_v5",
        dict(
            config_entry_id=entry.entry_id,
            expected_revision=entry.options["settings_revision"],
            expected_flow_plan_revision=entry.options["flow_plan_revision"],
            flow_plan=p,
            allowed_weekdays={s: list(DAYS) for s in STAGES},
            weekday=DAYS[__import__("homeassistant.util.dt", fromlist=["now"]).now().weekday()],
        ),
    )
    c = entry.runtime_data.control
    await start_native(hass, entry)
    await until(lambda: not c.running)
    capture(
        "preview-block-chain",
        dict(
            preview=preview,
            records=deepcopy(c.flow.records),
            calls=hass.data["p3_fixture"]["calls"],
        ),
    )
    assert c.flow.records["mix"]["result"] == "blocked_dependency"
    assert c.flow.records["nutrient"]["result"] == "blocked_dependency"
    assert preview["rows"][2]["eligibility"] == "blocked_dependency", (
        "Preview advertises eligible N although blocked predecessor can never supply finished anchor"
    )


@pytest.fixture(autouse=True)
def imports_provenance():
    yield
    import hashlib
    import sys

    entries = {}
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if path and (
            name.startswith("custom_components.uninus_nutriculture")
            or name
            in ("p2_fixtures", "p3_fixtures", "test_p3c_flow", "test_p3_dosing", "test_p2_control")
        ):
            entries[name] = {
                "path": path,
                "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            }
    capture("actual-imports", entries)


def suggested(form):
    return {
        str(k.schema): k.description["suggested_value"]
        for k in form["data_schema"].schema
        if k.description and "suggested_value" in k.description
    }


async def open_plan(hass, entry):
    form = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(form["flow_id"], {"flow_plan": True})


async def test_native_first_save_preview_cancel_busy_and_transition(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    before = deepcopy(dict(entry.options))
    form = await open_plan(hass, entry)
    payload = suggested(form)
    payload["action"] = "preview"
    form = await hass.config_entries.options.async_configure(form["flow_id"], payload)
    assert form["description_placeholders"]["preview"].count(":") == 7
    assert dict(entry.options) == before
    payload["action"] = "cancel"
    result = await hass.config_entries.options.async_configure(form["flow_id"], payload)
    assert result["type"] == "abort"
    assert dict(entry.options) == before
    await toggle(hass, entry, "automation_enabled")
    form = await open_plan(hass, entry)
    result = await hass.config_entries.options.async_configure(form["flow_id"], suggested(form))
    assert result["errors"]["base"] == "control_busy"
    assert entry.options["control_contract_version"] == 4
    await toggle(hass, entry, "automation_enabled", False)
    form = await open_plan(hass, entry)
    c = entry.runtime_data.control
    current = deepcopy(dict(entry.options))
    result = await hass.config_entries.options.async_configure(form["flow_id"], suggested(form))
    assert result["type"] == "create_entry"
    assert entry.options["control_contract_version"] == 5
    assert entry.options["settings_revision"] == current["settings_revision"] + 1
    assert entry.options["flow_plan_revision"] == 1
    assert entry.runtime_data.control is c
    assert not hass.data["p3_fixture"]["calls"]
    assert not hass.data["p2_fixture"]["calls"]


async def test_native_noop_and_stale_plan_cas_zero_write(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    before = deepcopy(dict(entry.options))
    form = await open_plan(hass, entry)
    result = await hass.config_entries.options.async_configure(form["flow_id"], suggested(form))
    assert result["type"] == "create_entry"
    assert dict(entry.options) == before
    form = await open_plan(hass, entry)
    p = plan()
    p["rows"][1]["delay_seconds"] = 3
    await save_v5(hass, entry, p)
    latest = deepcopy(dict(entry.options))
    result = await hass.config_entries.options.async_configure(form["flow_id"], suggested(form))
    assert result["errors"]["base"] == "settings_conflict"
    assert dict(entry.options) == latest


async def test_v5_legacy_settings_weekday_writer_is_rejected(dosing_hass):
    from homeassistant.exceptions import ServiceValidationError

    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    before = deepcopy(dict(entry.options))
    async with entry.runtime_data.lock:
        with pytest.raises(ServiceValidationError, match="settings_schema_mismatch"):
            entry.runtime_data.write_settings(
                control={
                    **before["control"],
                    "allowed_weekdays": {**before["control"]["allowed_weekdays"], "mix": ["mon"]},
                },
                expected_revision=before["settings_revision"],
            )
    assert dict(entry.options) == before


async def test_later_independent_refill_can_improve_waiting_mix(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    for i, stage in enumerate(("mix", "refill", "nutrient", "acid")):
        p["rows"][i].update(
            stage=stage,
            start_rule="flow_start" if i < 2 else "after_previous_finished",
            delay_seconds=0,
        )
    await save_v5(hass, entry, p)
    for key in ("automation_enabled", "mix_enabled", "refill_enabled"):
        await toggle(hass, entry, key)
    c = entry.runtime_data.control
    await start_native(hass, entry)
    try:
        await until(lambda: hass.data["p2_fixture"]["hardware"].is_on)
        assert c.flow.records["mix"]["phase"] == "waiting_condition"
        assert c.flow.records["mix"]["started_at"] is None and c.fault is None
        hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
        await until(lambda: c.flow.records["mix"]["started_at"] is not None)
        assert c.fault is None
    finally:
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize(
    "rule,expected",
    [("after_previous_started", "blocked_dependency"), ("after_previous_finished", "eligible")],
)
async def test_preview_skip_both_anchor_rules(dosing_hass, rule, expected):
    from homeassistant.util import dt as dt_util

    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    p["rows"][1].update(start_rule=rule, delay_seconds=0)
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "mix_enabled")
    r = await call(
        hass,
        "preview_flow_plan_v5",
        dict(
            config_entry_id=entry.entry_id,
            expected_revision=entry.options["settings_revision"],
            expected_flow_plan_revision=entry.options["flow_plan_revision"],
            flow_plan=p,
            allowed_weekdays={s: list(DAYS) for s in STAGES},
            weekday=DAYS[dt_util.now().weekday()],
        ),
    )
    assert r["rows"][1]["eligibility"] == expected
    assert r["rows"][1]["earliest_offset_seconds"] is None
    assert not hass.data["p3_fixture"]["calls"]
