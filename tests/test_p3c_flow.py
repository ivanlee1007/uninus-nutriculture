"""Native P3c Save/Preview/dispatch tracer; fake physical equipment only."""

import asyncio
import json
from pathlib import Path

import pytest
from homeassistant.exceptions import ServiceValidationError
from p3_fixtures import nutrient_payload
from test_p2_control import add_tank, target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native

STAGES = ("refill", "nutrient", "acid", "mix")
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def plan():
    return {
        "rows": [
            dict(
                stage=s,
                start_rule="flow_start"
                if i == 0
                else "after_previous_started"
                if s == "mix"
                else "after_previous_finished",
                delay_seconds=1 if s == "mix" else 0,
                condition=None,
                wait_timeout_seconds=20,
            )
            for i, s in enumerate(("refill", "mix", "nutrient", "acid"))
        ],
        "run_timeout_seconds": 120,
    }


async def prepared(hass):
    from homeassistant.components.switch import SwitchEntity
    from homeassistant.helpers import entity_registry as er

    class Acid(SwitchEntity):
        _attr_name = "P3c acid"
        _attr_unique_id = "p3c-acid"
        _attr_should_poll = False
        _attr_is_on = False

        def __init__(self):
            self.entered_on = asyncio.Event()

        async def async_turn_on(self, **kwargs):
            self._attr_is_on = True
            self.async_write_ha_state()
            self.entered_on.set()

        async def async_turn_off(self, **kwargs):
            self._attr_is_on = False
            self.async_write_ha_state()

    acid = Acid()
    await hass.data["switch"].async_add_entities([acid])
    entry = await add_tank(hass)
    values = nutrient_payload(hass)
    values.update(
        feedback_timeout=1,
        device_max_on_seconds=3,
        pulse_seconds=2,
        post_mix_seconds=1,
        sample_wait_timeout_seconds=15,
        stable_samples=1,
        stable_interval_seconds=1,
        flow_timeout_seconds=60,
        acid_output=er.async_get(hass).async_get(acid.entity_id).entity_id,
        acid_commissioned=True,
        acid_device_max_on_seconds=3,
        acid_protection_confirmed=True,
        acid_alias_notes="independent acid",
        acid_sample_mode="sequence",
        acid_sample_attribute="sample",
        acid_report_contract_confirmed=False,
        circulation_device_max_on_seconds=1800,
        circulation_protection_confirmed=True,
        circulation_alias_notes="independent cutoff",
        mix_commissioned=True,
        mix_safe_min_level_m=0.5,
        mix_flow_timeout_seconds=1200,
    )
    for key in (
        "safe_min_level_m",
        "pulse_seconds",
        "max_total_on_seconds",
        "max_pulses",
        "post_mix_seconds",
        "sample_wait_timeout_seconds",
        "stable_samples",
        "stable_interval_seconds",
        "flow_timeout_seconds",
    ):
        values["acid_" + key] = values[key]
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    saved = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert saved["type"] == "create_entry", saved
    assert entry.options["control_contract_version"] == 4
    hass.states.async_set("sensor.ph", "6.5", {"sample": 1})
    hass.states.async_set("sensor.ec", ".7", {"unit_of_measurement": "mS/cm"})
    hass.states.async_set("sensor.level", ".2", {"unit_of_measurement": "m"})
    return entry, acid


async def call(hass, service, payload):
    return await hass.services.async_call(
        "uninus_nutriculture", service, payload, blocking=True, return_response=True
    )


async def until(predicate, seconds=5):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_v4_retains_multistage_rejection(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "refill_enabled")
    await toggle(hass, entry, "mix_enabled")
    with pytest.raises(ServiceValidationError, match="flow_configuration_unsupported"):
        await start_native(hass, entry)
    assert not hass.data["p2_fixture"]["calls"]
    assert not hass.data["p3_fixture"]["calls"]


async def test_native_v5_services_have_exact_operable_descriptors(dosing_hass):
    from homeassistant.helpers import service

    hass = dosing_hass
    await add_tank(hass)
    all_services = (await service.async_get_all_descriptions(hass))["uninus_nutriculture"]
    assert set(all_services["apply_flow_plan_v5"]["fields"]) == {
        "config_entry_id",
        "expected_revision",
        "expected_flow_plan_revision",
        "flow_plan",
        "allowed_weekdays",
    }
    assert set(all_services["preview_flow_plan_v5"]["fields"]) == {
        "config_entry_id",
        "expected_revision",
        "expected_flow_plan_revision",
        "flow_plan",
        "allowed_weekdays",
        "weekday",
    }
    assert set(all_services["apply_control_settings_v5"]["fields"]) == {
        "config_entry_id",
        "expected_revision",
        "parameters",
        "dosing_parameters",
        "acid_parameters",
        "mix_parameters",
        "safety_parameters",
    }


async def test_weekday_waits_for_actual_resource_admission(dosing_hass):
    from homeassistant.util import dt as dt_util

    hass = dosing_hass
    entry, acid = await prepared(hass)
    p = plan()
    order = ("nutrient", "acid", "refill", "mix")
    for i, row in enumerate(p["rows"]):
        row.update(
            stage=order[i],
            start_rule="flow_start"
            if i == 0
            else "after_previous_started"
            if i == 1
            else "after_previous_finished",
            delay_seconds=0,
        )
    future_day = DAYS[(dt_util.now().weekday() + 1) % 7]
    days = {s: list(DAYS) for s in STAGES}
    days["acid"] = [future_day]
    await save_v5(hass, entry, p, days)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "nutrient_enabled")
    await toggle(hass, entry, "acid_enabled")
    c = entry.runtime_data.control
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(hass.data["p3_fixture"]["outputs"][0].entered_on.wait(), 3)
        await until(
            lambda: (
                c.flow.records["acid"]["phase"] == "waiting_resource"
                or c.flow.records["acid"]["result"] is not None
            )
        )
        assert c.flow.records["acid"]["result"] is None
        assert c.flow.records["acid"]["phase"] == "waiting_resource"
        # Domain-only HA-local admission-day seam, never patch SDK time functions.
        c.flow.weekday = lambda: future_day
        hass.states.async_set("sensor.ec", ".86", {"unit_of_measurement": "mS/cm"})
        await until(lambda: c.nutrient_stage.phase == "waiting_sample")
        hass.states.async_set("sensor.ec", ".87", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(acid.entered_on.wait(), 3)
        assert c.flow.records["nutrient"]["result"] == "completed"
    finally:
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize("entrance", ["service", "switch"])
async def test_native_save_preview_four_stage_overlap_terminal(dosing_hass, entrance):
    hass = dosing_hass
    entry, acid = await prepared(hass)
    payload = dict(
        config_entry_id=entry.entry_id,
        expected_revision=entry.options.get("settings_revision", 0),
        expected_flow_plan_revision=0,
        flow_plan=plan(),
        allowed_weekdays={s: list(DAYS) for s in STAGES},
    )
    response = await call(hass, "apply_flow_plan_v5", payload)
    assert response["applied"] and entry.options["control_contract_version"] == 5
    for key in ("expected_revision", "expected_flow_plan_revision"):
        payload[key] = response[
            "settings_revision" if key == "expected_revision" else "flow_plan_revision"
        ]
    await toggle(hass, entry, "automation_enabled")
    for stage in STAGES:
        await toggle(hass, entry, stage + "_enabled")
    for day in DAYS:
        preview = await call(hass, "preview_flow_plan_v5", {**payload, "weekday": day})
        assert preview["weekday"] == day
        assert preview["rows"][1]["eligibility"] == "eligible"
        assert preview["rows"][2]["earliest_offset_seconds"] is None
    # Explicit domain clock seam: public legal mix_duration remains unchanged.
    c = entry.runtime_data.control
    real_clock = c.mix_stage.clock
    c.mix_stage.clock = lambda: real_clock() * 600
    if entrance == "service":
        accepted = await start_native(hass, entry)
        assert accepted["accepted"]
    else:
        await toggle(hass, entry, "flow_run")
    pump, circ = hass.data["p3_fixture"]["outputs"]
    refill = hass.data["p2_fixture"]["hardware"]
    try:
        await until(lambda: refill.is_on)
        hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
        await asyncio.wait_for(circ.entered_on.wait(), 3)
        assert refill.is_on and circ.is_on
        await until(lambda: c.flow.records["mix"]["result"] == "completed")
        assert refill.is_on and not circ.is_on
        hass.states.async_set("sensor.level", "2.4", {"unit_of_measurement": "m"})
        await asyncio.wait_for(pump.entered_on.wait(), 3)
        hass.states.async_set("sensor.ec", ".86", {"unit_of_measurement": "mS/cm"})
        await until(lambda: c.nutrient_stage.phase == "waiting_sample")
        hass.states.async_set("sensor.ec", ".87", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(acid.entered_on.wait(), 3)
        hass.states.async_set("sensor.ph", "5.6", {"sample": 2})
        await until(lambda: c.acid_stage.phase == "waiting_sample")
        hass.states.async_set("sensor.ph", "5.6", {"sample": 3})
        await until(lambda: not c.running)
        status = dict(hass.states.get(target(hass, entry, "sensor", "control_status")).attributes)
        for key in ("friendly_name", "icon", "device_class", "options"):
            status.pop(key, None)

        assert len(status) == 30 and status["schema_version"] == 5
        assert status["flow_state"] == "completed" and status["fault"] is None
        assert all(v["result"] == "completed" for v in status["step_runtime"].values())
        assert set(status["output_states"]) == {"refill", "nutrient", "acid", "circulation"}
        assert all(v == "off" for v in status["output_states"].values())
        (Path(__file__).parents[1] / ("p3c-terminal-" + entrance + ".json")).write_text(
            json.dumps(status, default=str, indent=2)
        )
    finally:
        await toggle(hass, entry, "flow_run", False)


async def save_v5(hass, entry, flow_plan=None, weekdays=None):
    return await call(
        hass,
        "apply_flow_plan_v5",
        dict(
            config_entry_id=entry.entry_id,
            expected_revision=entry.options.get("settings_revision", 0),
            expected_flow_plan_revision=entry.options.get("flow_plan_revision", 0),
            flow_plan=flow_plan or plan(),
            allowed_weekdays=weekdays or {s: list(DAYS) for s in STAGES},
        ),
    )


def settings_payload(entry):
    return {
        "config_entry_id": entry.entry_id,
        "expected_revision": entry.options.get("settings_revision", 0),
        **{
            k: entry.options.get(
                k, dict(entry.runtime_data.parameters) if k == "parameters" else None
            )
            for k in (
                "parameters",
                "dosing_parameters",
                "acid_parameters",
                "mix_parameters",
                "safety_parameters",
            )
        },
    }


async def test_v5_registered_numeric_writer_and_plan_cas(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    from copy import deepcopy

    before = deepcopy(dict(entry.options))
    await save_v5(hass, entry)
    assert dict(entry.options) == before
    payload = settings_payload(entry)
    payload["parameters"] = {**entry.runtime_data.parameters, "ph_high": 5.9}
    result = await call(hass, "apply_control_settings_v5", payload)
    assert result["settings_revision"] == before["settings_revision"] + 1
    assert entry.options["flow_plan_revision"] == before["flow_plan_revision"]
    assert entry.options["control_contract_version"] == 5
    with pytest.raises(ServiceValidationError, match="settings_conflict"):
        await call(hass, "apply_control_settings_v5", payload)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": target(hass, entry, "number", "ph_high"), "value": 6.0},
        blocking=True,
    )
    assert entry.options["parameters"]["ph_high"] == 6.0
    assert entry.options["settings_revision"] == result["settings_revision"] + 1


async def test_two_circ_owners_first_completion_never_turns_off_other(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    order = ("nutrient", "mix", "refill", "acid")
    for i, row in enumerate(p["rows"]):
        row.update(
            stage=order[i],
            start_rule="flow_start"
            if i == 0
            else "after_previous_started"
            if i == 1
            else "after_previous_finished",
            delay_seconds=0,
        )
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "nutrient_enabled")
    await toggle(hass, entry, "mix_enabled")
    c = entry.runtime_data.control
    clock = c.mix_stage.clock
    c.mix_stage.clock = lambda: clock() * 600
    pump, circ = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    try:
        await until(lambda: len(c.leases) == 2)
        cutoff = c.flow.circ_cutoff
        assert hass.data["p3_fixture"]["calls"].count(("circulation", "on")) == 1
        await until(lambda: c.flow.records["mix"]["result"] == "completed")
        assert circ.is_on and len(c.leases) == 1
        assert c.flow.circ_cutoff == cutoff
        assert ("circulation", "off") not in hass.data["p3_fixture"]["calls"]
        hass.states.async_set("sensor.ec", ".86", {"unit_of_measurement": "mS/cm"})
        await until(lambda: c.nutrient_stage.phase == "waiting_sample")
        hass.states.async_set("sensor.ec", ".87", {"unit_of_measurement": "mS/cm"})
        await until(lambda: not c.running)
        assert not circ.is_on and not pump.is_on and not c.leases
        assert c.flow.records["nutrient"]["result"] == "completed"
        assert c.flow.records["refill"]["result"] == "skipped_disabled"
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_v5_pending_circ_on_does_not_block_independent_safety_off(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    p["rows"][1].update(start_rule="flow_start", delay_seconds=0)
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    pump, circ = hass.data["p3_fixture"]["outputs"]
    circ.on_apply_gate = asyncio.Event()
    try:
        await start_native(hass, entry)
        await asyncio.wait_for(circ.entered_on.wait(), 3)
        request = asyncio.create_task(toggle(hass, entry, "flow_run", False))
        await asyncio.wait_for(circ.entered_off.wait(), 0.75)
        assert not circ.on_apply_gate.is_set()
        assert entry.runtime_data.control.running
    finally:
        circ.on_apply_gate.set()
        if "request" in locals():
            await asyncio.wait_for(request, 5)
        await toggle(hass, entry, "flow_run", False)
    await until(lambda: not entry.runtime_data.control.running)
    assert not circ.is_on


async def test_active_plan_save_keeps_controller_and_run_snapshot(dosing_hass):
    from copy import deepcopy

    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "refill_enabled")
    c = entry.runtime_data.control
    await start_native(hass, entry)
    try:
        await until(lambda: hass.data["p2_fixture"]["hardware"].is_on)
        accepted = deepcopy(c.flow.run_plan)
        p = plan()
        p["rows"][1]["delay_seconds"] = 7
        days = {s: [] for s in STAGES}
        await save_v5(hass, entry, p, days)
        assert entry.runtime_data.control is c
        assert c.flow.run_plan == accepted
        assert entry.options["flow_plan"] == p
        assert c.running
    finally:
        await toggle(hass, entry, "flow_run", False)
    assert not hass.data["p2_fixture"]["hardware"].is_on


@pytest.mark.parametrize(
    "rule,expected",
    [("after_previous_started", "blocked_dependency"), ("after_previous_finished", "completed")],
)
async def test_skip_anchor_no_fabricated_started(dosing_hass, rule, expected):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    p["rows"][1].update(start_rule=rule, delay_seconds=0)
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    c = entry.runtime_data.control
    clock = c.mix_stage.clock
    c.mix_stage.clock = lambda: clock() * 600
    await start_native(hass, entry)
    await until(lambda: not c.running)
    assert c.flow.records["refill"]["result"] == "skipped_disabled"
    assert c.flow.records["refill"]["started_at"] is None
    assert c.flow.records["mix"]["result"] == expected


async def test_admission_wait_is_not_execution_deadline(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    p["rows"][1].update(start_rule="flow_start", delay_seconds=0, wait_timeout_seconds=1)
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    c = entry.runtime_data.control
    clock = c.mix_stage.clock
    c.mix_stage.clock = lambda: clock() * 300
    await start_native(hass, entry)
    await until(lambda: not c.running)
    assert c.flow.records["mix"]["result"] == "completed"
    assert c.fault is None


@pytest.mark.parametrize(
    "bad", ["repeat", "first_rule", "bool_delay", "nan_condition", "extra_condition", "extra_plan"]
)
async def test_static_save_rejects_bad_plan_atomic(dosing_hass, bad):
    from copy import deepcopy

    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    if bad == "repeat":
        p["rows"][2]["stage"] = "refill"
    elif bad == "first_rule":
        p["rows"][0]["start_rule"] = "after_previous_started"
    elif bad == "bool_delay":
        p["rows"][1]["delay_seconds"] = True
    elif bad == "nan_condition":
        p["rows"][1]["condition"] = dict(source="level", operator="gte", value=float("nan"))
    elif bad == "extra_condition":
        p["rows"][1]["condition"] = dict(
            source="level", operator="gte", value=1, entity_id="sensor.secret"
        )
    else:
        p["extra"] = True
    old = deepcopy(dict(entry.options))
    with pytest.raises(ServiceValidationError):
        await save_v5(hass, entry, p)
    assert dict(entry.options) == old
    assert not hass.data["p3_fixture"]["calls"]


async def test_preview_draft_weekdays_and_dynamic_safety_are_truthful(dosing_hass):
    from copy import deepcopy

    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    old = deepcopy(dict(entry.options))
    p = plan()
    p["rows"][1].update(start_rule="flow_start", delay_seconds=0)
    days = {s: list(DAYS) for s in STAGES}
    payload = dict(
        config_entry_id=entry.entry_id,
        expected_revision=old["settings_revision"],
        expected_flow_plan_revision=old["flow_plan_revision"],
        flow_plan=p,
        allowed_weekdays=days,
        weekday="mon",
    )
    result = await call(hass, "preview_flow_plan_v5", payload)
    assert result["rows"][1]["eligibility"] == "blocked_safety"
    days["mix"] = ["tue"]
    result = await call(hass, "preview_flow_plan_v5", payload)
    assert result["rows"][1]["eligibility"] == "skipped_weekday"
    assert dict(entry.options) == old
    assert not hass.data["p3_fixture"]["calls"]


async def test_v5_reset_fault_clears_global_not_step_outcome(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    p["rows"][1].update(start_rule="flow_start", delay_seconds=0)
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "mix_enabled")
    c = entry.runtime_data.control
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(hass.data["p3_fixture"]["outputs"][1].entered_on.wait(), 3)
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": target(hass, entry, "button", "emergency_stop")},
            blocking=True,
        )
        assert c.fault == "emergency_stop"
        assert not c.running
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": target(hass, entry, "button", "reset_fault")},
            blocking=True,
        )
        assert c.fault is None and c.flow_state == "disabled"
        assert c.flow.records["mix"]["result"] == "fault"
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_pending_stage_cannot_adopt_relaxed_accepted_budget(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    p = plan()
    p["rows"][0].update(stage="nutrient", delay_seconds=1)
    p["rows"][2].update(stage="refill")
    await save_v5(hass, entry, p)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "nutrient_enabled")
    c = entry.runtime_data.control
    await start_native(hass, entry)
    try:
        payload = settings_payload(entry)
        payload["dosing_parameters"] = {**entry.options["dosing_parameters"], "max_pulses": 10}
        await call(hass, "apply_control_settings_v5", payload)
        await asyncio.wait_for(hass.data["p3_fixture"]["outputs"][0].entered_on.wait(), 3)
        assert c.nutrient_stage.settings["max_pulses"] == 5
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_queued_start_is_revoked_by_flow_off(dosing_hass):
    hass = dosing_hass
    entry, _ = await prepared(hass)
    await save_v5(hass, entry)
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "refill_enabled")
    await entry.runtime_data.lock.acquire()
    request = asyncio.create_task(start_native(hass, entry))
    try:
        await until(lambda: bool(entry.runtime_data.lock._waiters))
        await toggle(hass, entry, "flow_run", False)
    finally:
        entry.runtime_data.lock.release()
    with pytest.raises(ServiceValidationError, match="revoked"):
        await request
    assert not hass.data["p2_fixture"]["calls"]
