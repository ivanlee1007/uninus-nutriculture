"""Native regressions for necessary-source invalidation during pending ON."""

import asyncio

import pytest
from homeassistant.exceptions import ServiceValidationError
from test_p2_control import add_tank, configure, toggle


@pytest.mark.parametrize(
    "source,value,unit", [("ph", 5.6, "pH"), ("ec", 0.85, "mS/cm"), ("level", 2, "m")]
)
@pytest.mark.parametrize("recover", [False, True])
async def test_invalid_source_during_applied_on_cannot_be_forgotten(
    control_hass, recover, source, value, unit
):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=2)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware.on_entered, hardware.on_release = asyncio.Event(), asyncio.Event()
    start = asyncio.create_task(toggle(hass, tank, "flow_run"))
    await asyncio.wait_for(hardware.on_entered.wait(), 2)
    # Applied physical ON precedes the provider's API return, as in the review.
    hardware._attr_is_on = True
    hardware.async_write_ha_state()
    await asyncio.sleep(0.05)
    hass.states.async_set("sensor." + source, "unavailable")
    await asyncio.sleep(0.10)  # Drain event/evaluate work without awaiting blocked ON.
    if recover:
        hass.states.async_set("sensor." + source, value, {"unit_of_measurement": unit})
        await asyncio.sleep(0.05)
    hardware.on_release.set()
    result = (await asyncio.gather(start, return_exceptions=True))[0]
    await hass.async_block_till_done()
    try:
        assert isinstance(result, ServiceValidationError), (
            "Observed source invalidation must revoke admitted ON despite recovery"
        )
        assert hass.states.get(hardware.entity_id).state == "off"
        control = tank.runtime_data.control
        assert control.fault == "source_invalid"
        assert control.flow_state == "fault"
        assert not control.running
        calls = hass.data["p2_fixture"]["calls"]
        assert [call[0] for call in calls] == ["turn_on", "turn_off"]
        assert calls[-1][2].parent_id == calls[0][2].id
    finally:
        await toggle(hass, tank, "flow_run", False)


async def test_same_transient_source_invalid_after_start_is_latched(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=2)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    await toggle(hass, tank, "flow_run")
    hardware = hass.data["p2_fixture"]["hardware"]
    hass.states.async_set("sensor.ph", "unavailable")
    await asyncio.sleep(0.1)
    hass.states.async_set("sensor.ph", 5.6, {"unit_of_measurement": "pH"})
    await hass.async_block_till_done()
    assert tank.runtime_data.control.fault == "source_invalid"
    assert not tank.runtime_data.control.running
    assert hass.states.get(hardware.entity_id).state == "off"


async def test_ordinary_start_waits_for_on_without_output_fault(control_hass):
    hass = control_hass
    tank = await add_tank(hass)
    await configure(hass, tank, feedback_timeout=2)
    await toggle(hass, tank, "automation_enabled")
    await toggle(hass, tank, "refill_enabled")
    hardware = hass.data["p2_fixture"]["hardware"]
    hardware.on_entered, hardware.on_release = asyncio.Event(), asyncio.Event()
    start = asyncio.create_task(toggle(hass, tank, "flow_run"))
    await asyncio.wait_for(hardware.on_entered.wait(), 2)
    # Valid source change schedules evaluate while physical output is still OFF.
    hass.states.async_set("sensor.ph", 5.7, {"unit_of_measurement": "pH"})
    await asyncio.sleep(0.1)
    assert hass.states.get(hardware.entity_id).state == "off"
    assert tank.runtime_data.control.flow_state == "starting"
    assert tank.runtime_data.control.fault is None
    hardware.on_release.set()
    await start
    await hass.async_block_till_done()
    assert tank.runtime_data.control.flow_state == "refilling"
    assert tank.runtime_data.control.running
    assert tank.runtime_data.control.fault is None
    assert hass.states.get(hardware.entity_id).state == "on"
    await toggle(hass, tank, "flow_run", False)
