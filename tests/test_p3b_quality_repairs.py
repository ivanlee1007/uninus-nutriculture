"""Independent native boundary probes; production and old tests remain read-only."""

import asyncio
import copy
import json

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from p3_fixtures import nutrient_payload
from test_p2_control import add_tank, target
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3b_native import acid_values, save_acid

OUT = None


@pytest.mark.parametrize("invalid_role", ["acid", "circulation"])
async def test_emergency_invalid_idle_role_closes_valid_owners(dosing_hass, tmp_path, invalid_role):
    OUT = tmp_path
    hass = dosing_hass
    nutrient, circ = hass.data["p3_fixture"]["outputs"]
    acid = type(nutrient)("quality_acid")
    foreign = type(nutrient)("quality_foreign")
    await hass.data["switch"].async_add_entities([acid, foreign])
    refill = hass.data["p2_fixture"]["hardware"]
    entry = await add_tank(hass)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": target(hass, entry, "number", "mix_duration"), "value": 1},
        blocking=True,
    )
    values = {**nutrient_payload(hass), **acid_values(hass)}
    values.update(
        acid_output=acid.entity_id,
        mix_commissioned=True,
        mix_safe_min_level_m=0.5,
        mix_flow_timeout_seconds=120,
        circulation_device_max_on_seconds=90,
        post_mix_seconds=1,
        sample_wait_timeout_seconds=5,
        stable_samples=1,
        stable_interval_seconds=1,
        flow_timeout_seconds=20,
    )
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    c = entry.runtime_data.control
    assert (
        c.supports_nutrient
        and c.supports_acid
        and c.supports_mix
        and entry.options["control"]["commissioned"]
    )
    outputs = {"nutrient": nutrient, "acid": acid, "circulation": circ, "refill": refill}
    registry = er.async_get(hass)
    assert len({registry.async_get(o.entity_id).id for o in outputs.values()}) == 4
    for output in (*outputs.values(), foreign):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": output.entity_id}, blocking=True
        )
    # The acid Registry identity is no longer ours. Never send OFF to its replacement.
    replacement = outputs[invalid_role]
    registry.async_update_entity(replacement.entity_id, new_unique_id="quality_foreign_replacement")
    await asyncio.sleep(0.05)
    before = copy.deepcopy(dict(entry.options))
    error = None
    try:
        try:
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": target(hass, entry, "button", "emergency_stop")},
                blocking=True,
            )
        except Exception as exc:
            error = str(exc)
        await asyncio.sleep(0.2)
        states = {name: output.is_on for name, output in outputs.items()}
        owners = {
            name: {"owns_io": stage.owns_io, "operations": [str(key) for key in stage.operations]}
            for name, stage in [
                ("nutrient", c.nutrient_stage),
                ("acid", c.acid_stage),
                ("mix", c.mix_stage),
            ]
        }
        receipt = {
            "error": error,
            "outputs_on": states,
            "foreign_on": foreign.is_on,
            "foreign_off": foreign.entered_off.is_set(),
            "acid_replacement_off": acid.entered_off.is_set(),
            "owners": owners,
            "running": c.running,
            "fault": c.fault,
            "persisted_control": dict(entry.options["control"]),
            "calls": hass.data["p3_fixture"]["calls"],
            "refill_calls": hass.data["p2_fixture"]["calls"],
        }
        (OUT / "emergency-identity.json").write_text(
            json.dumps(receipt, indent=2, default=str), encoding="utf-8"
        )
        # Assert durable fault and foreign/identity boundary independently from closure.
        assert c.fault == "emergency_stop" and entry.options["control"]["fault"] == "emergency_stop"
        assert not entry.options["control"]["automation_enabled"] and not c.master
        assert entry.options["settings_revision"] == before["settings_revision"]
        assert foreign.is_on and not foreign.entered_off.is_set()
        assert replacement.is_on and not replacement.entered_off.is_set()
        assert all(
            binding == entry.options["control"][key]
            for key, binding in before["control"].items()
            if key.endswith("binding")
        )
        assert not any(states[name] for name in outputs if name != invalid_role), receipt
        assert c.running
        assert c.acid_stage.owns_io
        if invalid_role == "circulation":
            assert c.nutrient_stage.owns_io and c.mix_stage.owns_io
        else:
            assert not c.nutrient_stage.owns_io and not c.mix_stage.owns_io
        await hass.async_block_till_done()
        state = hass.states.get(target(hass, entry, "sensor", "control_status"))
        assert state.attributes["output_states"][invalid_role] == "unknown"
        assert state.attributes["fault"] == "emergency_stop"
    finally:
        # Fixture-only cleanup after evidence, not counted as production closure.
        for output in (*outputs.values(), foreign):
            await hass.services.async_call(
                "switch", "turn_off", {"entity_id": output.entity_id}, blocking=True
            )


async def test_acid_only_global_high_ph_alarm(dosing_hass, tmp_path):
    OUT = tmp_path
    hass = dosing_hass
    entry = await add_tank(hass)
    await save_acid(hass, entry)
    c = entry.runtime_data.control
    assert c.supports_acid and not c.supports_nutrient
    before = copy.deepcopy(dict(entry.options))
    now = [0.0]
    c.acid_stage.clock = lambda: now[0]
    c.nutrient_stage.clock = lambda: now[0]
    hass.states.async_set("sensor.ph", "7.0", {"sample": 42})
    await hass.async_block_till_done()
    c.update_ph_alarm()
    now[0] = entry.options["safety_parameters"]["ph_high_alarm_seconds"] + 1
    c.update_ph_alarm()
    (OUT / "acid-alarm.json").write_text(
        json.dumps(
            {
                "alarm": c.ph_high_alarm_active,
                "since": c.ph_high_since,
                "acid_only": True,
                "seconds": now[0],
                "safety": dict(entry.options["safety_parameters"]),
                "calls": hass.data["p3_fixture"]["calls"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert dict(entry.options) == before
    assert not c.running and not any(
        stage.owns_io for stage in (c.nutrient_stage, c.acid_stage, c.mix_stage)
    )
    assert not hass.data["p3_fixture"]["calls"] and not hass.data["p2_fixture"]["calls"]
    assert c.ph_high_alarm_active, "Global S high-pH alarm must work with acid-only commissioning"
    await hass.async_block_till_done()
    state = hass.states.get(target(hass, entry, "sensor", "control_status"))
    assert state.attributes["reasons"].count("ph_high_alarm") == 1
    hass.states.async_set("sensor.ph", "unknown")
    await hass.async_block_till_done()
    assert not c.ph_high_alarm_active and c.ph_high_since is None
    hass.states.async_set("sensor.ph", "7.0", {"unit_of_measurement": "invalid"})
    await hass.async_block_till_done()
    assert not c.ph_high_alarm_active and c.ph_high_since is None


async def test_v4_does_not_drop_active_global_alarm_from_native_sensor(dosing_hass, tmp_path):
    hass = dosing_hass
    entry = await add_tank(hass)
    values = nutrient_payload(hass)
    values.update(
        ph_high_alarm_seconds=1,
        post_mix_seconds=1,
        stable_samples=1,
        stable_interval_seconds=1,
        flow_timeout_seconds=20,
    )
    values["acid_pulse_seconds"] = 3
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert result["type"] == FlowResultType.CREATE_ENTRY, result
    assert entry.options["control_contract_version"] == 4
    c = entry.runtime_data.control
    assert c.supports_nutrient
    before = copy.deepcopy(dict(entry.options))
    now = [0.0]
    c.nutrient_stage.clock = lambda: now[0]
    hass.states.async_set("sensor.ph", "7.0", {"unit_of_measurement": "pH"})
    await hass.async_block_till_done()
    c.update_ph_alarm()
    assert c.ph_high_since == 0
    now[0] = 2.0
    c.update_ph_alarm()
    await hass.async_block_till_done()
    state = hass.states.get(target(hass, entry, "sensor", "control_status"))
    receipt = {
        "schema_version": state.attributes["schema_version"],
        "alarm_active": c.ph_high_alarm_active,
        "reasons": state.attributes["reasons"],
        "persist_unchanged": dict(entry.options) == before,
        "calls": hass.data["p3_fixture"]["calls"],
    }
    (tmp_path / "alarm-projection.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    assert c.ph_high_alarm_active
    assert dict(entry.options) == before and not c.running
    assert not hass.data["p3_fixture"]["calls"] and not hass.data["p2_fixture"]["calls"]
    assert state.attributes["schema_version"] == 4
    assert "ph_high_alarm" in state.attributes["reasons"], receipt


async def test_mix_only_global_ph_observer_ignores_other_quality(dosing_hass):
    hass = dosing_hass
    entry = await add_tank(hass)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": target(hass, entry, "number", "mix_duration"), "value": 1},
        blocking=True,
    )
    values = acid_values(hass)
    values.update(
        acid_commissioned=False,
        mix_commissioned=True,
        mix_safe_min_level_m=0.5,
        mix_flow_timeout_seconds=120,
        circulation_device_max_on_seconds=90,
        ph_high_alarm_seconds=1,
    )
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    assert result["type"] == FlowResultType.CREATE_ENTRY, result
    c = entry.runtime_data.control
    assert c.supports_mix and not c.supports_nutrient and not c.supports_acid
    before = copy.deepcopy(dict(entry.options))
    now = [0.0]
    c.nutrient_stage.clock = lambda: now[0]
    hass.states.async_set("sensor.ec", "unknown")
    hass.states.async_set("sensor.level", "unknown")
    hass.states.async_set("sensor.ph", "7.0", {"unit_of_measurement": "pH"})
    await hass.async_block_till_done()
    c.update_ph_alarm()
    assert c.ph_high_since == 0
    now[0] = 2
    c.update_ph_alarm()
    await hass.async_block_till_done()
    state = hass.states.get(target(hass, entry, "sensor", "control_status"))
    assert state.attributes["reasons"].count("ph_high_alarm") == 1
    assert c.ph_high_alarm_active and not c.running
    assert dict(entry.options) == before
    assert not hass.data["p3_fixture"]["calls"] and not hass.data["p2_fixture"]["calls"]
