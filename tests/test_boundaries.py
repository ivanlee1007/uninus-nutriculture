"""Supplementary boundary coverage of already-green quality behavior."""

import json
from pathlib import Path

import pytest
from conftest import entry
from test_writes import ids


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("ph", 5.4, "within_range"),
        ("ph", 5.8, "within_range"),
        ("ph", 5.3, "out_of_range"),
        ("ec", 0.8, "within_range"),
        ("ec", 0.9, "within_range"),
        ("ec", 0.79, "out_of_range"),
        ("level", 2.25, "within_range"),
        ("level", 2.4, "within_range"),
        ("level", 2.41, "out_of_range"),
    ],
)
async def test_all_three_inclusive_ranges(hass, key, value, expected):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    source = hass.states.get("sensor." + key)
    hass.states.async_set(source.entity_id, value, source.attributes)
    await hass.async_block_till_done()
    state = hass.states.get(ids(hass, tank)["status"])
    assert state.state == expected
    assert state.attributes["ready_for_irrigation"] is False
    assert state.attributes["reasons"] == (
        [] if expected == "within_range" else [key + "_out_of_range"]
    )


async def test_missing_source_on_native_setup_is_invalid(hass):
    hass.states.async_remove("sensor.ph")
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    state = hass.states.get(ids(hass, tank)["status"])
    assert state.state == "invalid"
    assert state.attributes["reasons"] == ["ph_missing"]
    assert state.attributes["ready_for_irrigation"] is False


def test_metadata_and_translations():
    root = Path(__file__).resolve().parents[1]
    component = root / "custom_components" / "uninus_nutriculture"
    manifest = json.loads((component / "manifest.json").read_text())
    assert manifest["domain"] == "uninus_nutriculture"
    assert manifest["version"] == "0.2.0"
    assert manifest["config_flow"] is True
    assert manifest["requirements"] == []
    for file in ["strings.json", "translations/en.json", "translations/zh-Hant.json"]:
        content = json.loads((component / file).read_text(encoding="utf-8"))
        assert set(content["config"]["step"]["user"]["data"]) == {
            "name",
            "ph",
            "ec",
            "level",
            "max_age_seconds",
        }
        assert set(content["options"]["step"]["init"]["data"]) == {
            "ph",
            "ec",
            "level",
            "max_age_seconds",
            "refill_output",
            "commissioned",
            "feedback_timeout",
            "refill_weekdays",
            "nutrient_weekdays",
            "acid_weekdays",
            "mix_weekdays",
            # P3a native configuration extends, not removes, the P1/P2 fields.
            "nutrient_output",
            "circulation_output",
            "nutrient_commissioned",
            "nutrient_protection_confirmed",
            "device_max_on_seconds",
            "alias_notes",
            "sample_mode",
            "sample_attribute",
            "report_contract_confirmed",
            "safe_min_level_m",
            "pulse_seconds",
            "max_total_on_seconds",
            "max_pulses",
            "post_mix_seconds",
            "sample_wait_timeout_seconds",
            "stable_samples",
            "stable_interval_seconds",
            "flow_timeout_seconds",
            "ph_danger_low",
            "ec_danger_high",
            "ph_high_alarm",
            "ph_high_alarm_seconds",
            # P3b extends the exact set; no legacy key is removed.
            "acid_output",
            "acid_commissioned",
            "acid_device_max_on_seconds",
            "acid_protection_confirmed",
            "acid_alias_notes",
            "acid_sample_mode",
            "acid_sample_attribute",
            "acid_report_contract_confirmed",
            "mix_commissioned",
            "circulation_device_max_on_seconds",
            "circulation_protection_confirmed",
            "circulation_alias_notes",
            "acid_safe_min_level_m",
            "acid_pulse_seconds",
            "acid_max_total_on_seconds",
            "acid_max_pulses",
            "acid_post_mix_seconds",
            "acid_sample_wait_timeout_seconds",
            "acid_stable_samples",
            "acid_stable_interval_seconds",
            "acid_flow_timeout_seconds",
            "mix_safe_min_level_m",
            "mix_flow_timeout_seconds",
        }
        assert set(content["config"]["error"]) == {
            "invalid_name",
            "invalid_max_age",
            "invalid_source",
        }
