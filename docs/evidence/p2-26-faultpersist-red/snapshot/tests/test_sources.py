"""Source-event quality contract through real Core StateMachine."""

import pytest
from conftest import entry
from test_writes import ids


@pytest.mark.parametrize(
    ("reading", "unit", "expected", "reason"),
    [
        ("6.0", "pH", "out_of_range", "ph_out_of_range"),
        ("5.4", "pH", "within_range", None),
        ("5.8", "pH", "within_range", None),
        ("unknown", "pH", "invalid", "ph_invalid"),
        ("unavailable", "pH", "invalid", "ph_invalid"),
        ("bad", "pH", "invalid", "ph_invalid"),
        ("nan", "pH", "invalid", "ph_invalid"),
        ("inf", "pH", "invalid", "ph_invalid"),
        ("5.6", "wrong", "invalid", "ph_unit"),
        ("5.6", None, "within_range", None),
    ],
)
async def test_source_changes_publish_quality(hass, reading, unit, expected, reason):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    status_id = ids(hass, tank)["status"]
    hass.states.async_set("sensor.ph", reading, {"unit_of_measurement": unit})
    await hass.async_block_till_done()
    status = hass.states.get(status_id)
    assert status.state == expected
    assert status.attributes["reasons"] == ([] if reason is None else [reason])
    assert status.attributes["ready_for_irrigation"] is False


async def test_ec_microsiemens_is_rejected_not_misinterpreted(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.ec", 0.85, {"unit_of_measurement": "µS/cm"})
    await hass.async_block_till_done()
    state = hass.states.get(ids(hass, tank)["status"])
    assert state.state == "invalid"
    assert state.attributes["reasons"] == ["ec_unit"]


async def test_source_deletion_invalidates_status(hass):
    tank = entry()
    await hass.config_entries.async_add(tank)
    await hass.async_block_till_done()
    hass.states.async_remove("sensor.level")
    await hass.async_block_till_done()
    state = hass.states.get(ids(hass, tank)["status"])
    assert state.state == "invalid"
    assert state.attributes["reasons"] == ["level_missing"]
