"""First real native nutrient run: no refill binding, no browser timers.

These are fake physical switches behind the unmodified native HA dispatcher.
Unlike the settings-only fixture, this fixture explicitly expects actuation.
"""

import asyncio

import pytest
import pytest_asyncio
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import entity_registry as er
from p3_fixtures import nutrient_payload
from test_p2_control import add_tank, target, toggle


@pytest_asyncio.fixture
async def dosing_hass(control_hass):
    hass = control_hass
    calls = []
    contexts = []

    class Output(SwitchEntity):
        _attr_should_poll = False
        _attr_is_on = False

        def __init__(self, role):
            self.role = role
            self._attr_name = "Dosing fixture " + role
            self._attr_unique_id = "dosing-fixture-" + role
            self.entered_on = asyncio.Event()
            self.entered_off = asyncio.Event()
            self.cutoff = None
            self.on_ack_gate = None
            self.on_apply_gate = None
            self.off_ack_gate = None
            self.fail_off = False

        def local_cutoff(self):
            self.cutoff = None
            self._attr_is_on = False
            calls.append((self.role, "device_local_cutoff"))
            self.async_write_ha_state()

        async def async_turn_on(self, **kwargs):
            calls.append((self.role, "on"))
            contexts.append((self.role, "on", self._context))
            if self.on_apply_gate:
                self.entered_on.set()
                await self.on_apply_gate.wait()
            self._attr_is_on = True
            self.async_write_ha_state()
            self.entered_on.set()
            if self.role == "nutrient":
                self.cutoff = asyncio.get_running_loop().call_later(3, self.local_cutoff)
            if self.on_ack_gate:
                await self.on_ack_gate.wait()

        async def async_turn_off(self, **kwargs):
            calls.append((self.role, "off"))
            contexts.append((self.role, "off", self._context))
            if self.fail_off:
                self.entered_off.set()
                raise RuntimeError("fixture_off_failed")
            self._attr_is_on = False
            if self.cutoff:
                self.cutoff.cancel()
                self.cutoff = None
            self.async_write_ha_state()
            self.entered_off.set()
            if self.off_ack_gate:
                await self.off_ack_gate.wait()

    outputs = [Output(role) for role in ("nutrient", "circulation")]
    await hass.data["switch"].async_add_entities(outputs)
    hass.data["p3_fixture"] = {
        "outputs": outputs,
        "calls": calls,
        "contexts": contexts,
        "rows": [er.async_get(hass).async_get(output.entity_id) for output in outputs],
    }
    try:
        yield hass
    finally:
        for output in outputs:
            if output.cutoff:
                output.cutoff.cancel()


async def prepared(hass, **overrides):
    entry = await add_tank(hass)
    values = nutrient_payload(hass)
    values.pop("refill_output")
    values.update(
        commissioned=False,
        feedback_timeout=3,
        device_max_on_seconds=3,
        pulse_seconds=1,
        post_mix_seconds=1,
        sample_wait_timeout_seconds=3,
        stable_samples=1,
        stable_interval_seconds=1,
        flow_timeout_seconds=15,
    )
    values.update(overrides)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(flow["flow_id"], values)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.ec", "0.7", {"unit_of_measurement": "mS/cm"})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "nutrient_enabled")
    return entry


async def start_native(hass, entry):
    return await hass.services.async_call(
        "uninus_nutriculture",
        "start_flow",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )


async def test_pulse_deadline_starts_at_send_not_ack(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    pump, circulation = hass.data["p3_fixture"]["outputs"]
    pump.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        await asyncio.wait_for(pump.entered_off.wait(), 1.4)
        assert not pump.on_ack_gate.is_set()
        assert not pump.is_on
        assert entry.runtime_data.control.running, "Unsettled ON forbids restart"
    finally:
        pump.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)


async def test_pending_on_invalid_event_latches_even_after_recovery(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, circulation = hass.data["p3_fixture"]["outputs"]
    pump.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        hass.states.async_set("sensor.ec", "unavailable", {"unit_of_measurement": "mS/cm"})
        hass.states.async_set("sensor.ec", "0.7", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        assert entry.runtime_data.control.fault == "source_invalid"
        assert not pump.is_on
    finally:
        pump.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize(
    ("source", "bad", "good", "unit", "reason"),
    [
        ("level", "0.1", "1.0", "m", "level_unsafe"),
        ("ec", "1.4", "0.7", "mS/cm", "ec_danger"),
        ("ph", "3.7", "6.0", "pH", "ph_danger"),
    ],
)
async def test_pending_on_safety_event_latches_after_recovery(
    dosing_hass, source, bad, good, unit, reason
):
    hass = dosing_hass
    entry = await prepared(hass, pulse_seconds=2)
    pump, circulation = hass.data["p3_fixture"]["outputs"]
    pump.on_ack_gate = asyncio.Event()
    await start_native(hass, entry)
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 2)
        hass.states.async_set("sensor." + source, bad, {"unit_of_measurement": unit})
        hass.states.async_set("sensor." + source, good, {"unit_of_measurement": unit})
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        assert entry.runtime_data.control.fault == reason
        assert not pump.is_on
    finally:
        pump.on_ack_gate.set()
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize("budget", ["max_pulses", "max_total_on_seconds"])
async def test_max_pulses_blocks_second_dose_after_fresh_low_sample(dosing_hass, budget):
    hass = dosing_hass
    entry = await prepared(hass, **{budget: 1})
    pump, circulation = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    try:
        async with asyncio.timeout(4):
            while entry.runtime_data.control.flow_state != "waiting_sample":
                await asyncio.sleep(0.01)
        hass.states.async_set("sensor.ec", "0.71", {"unit_of_measurement": "mS/cm"})
        async with asyncio.timeout(1):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert entry.runtime_data.control.fault == "dose_budget_exhausted"
        assert hass.data["p3_fixture"]["calls"].count(("nutrient", "on")) == 1
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_reported_same_value_is_new_sample_after_barrier(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
    await start_native(hass, entry)
    try:
        async with asyncio.timeout(2):
            while entry.runtime_data.control.flow_state != "waiting_sample":
                await asyncio.sleep(0.01)
        hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
        async with asyncio.timeout(0.75):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert entry.runtime_data.control.flow_state == "completed"
        assert ("nutrient", "on") not in hass.data["p3_fixture"]["calls"]
    finally:
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize("mode", ["sequence", "timestamp"])
async def test_sample_token_not_attribute_repaint(dosing_hass, mode):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    hass = dosing_hass
    entry = await prepared(hass, sample_mode=mode, sample_attribute="sample")
    first = 1 if mode == "sequence" else (dt_util.utcnow() - timedelta(seconds=2)).isoformat()
    second = 2 if mode == "sequence" else (dt_util.utcnow() - timedelta(seconds=1)).isoformat()
    attrs = {"unit_of_measurement": "mS/cm", "sample": first}
    hass.states.async_set("sensor.ec", "0.86", attrs)
    await start_native(hass, entry)
    try:
        async with asyncio.timeout(2):
            while entry.runtime_data.control.flow_state != "waiting_sample":
                await asyncio.sleep(0.01)
        hass.states.async_set("sensor.ec", "0.86", {**attrs, "paint": True})
        await asyncio.sleep(0.15)
        assert entry.runtime_data.control.running, "Old token/repaint must not complete"
        hass.states.async_set("sensor.ec", "0.86", {**attrs, "sample": second})
        async with asyncio.timeout(1):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert entry.runtime_data.control.flow_state == "completed"
    finally:
        await toggle(hass, entry, "flow_run", False)


async def test_nutrient_only_emergency_reset_without_refill_binding(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass)
    pump, circulation = hass.data["p3_fixture"]["outputs"]
    await start_native(hass, entry)
    await asyncio.wait_for(pump.entered_on.wait(), 2)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": target(hass, entry, "button", "emergency_stop")},
        blocking=True,
    )
    assert not pump.is_on and not circulation.is_on
    assert entry.runtime_data.control.fault == "emergency_stop"
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": target(hass, entry, "button", "reset_fault")},
        blocking=True,
    )
    assert entry.runtime_data.control.fault is None
    assert not entry.runtime_data.control.master and not entry.runtime_data.control.running


async def test_flow_deadline_includes_waiting_for_new_sample(dosing_hass):
    hass = dosing_hass
    entry = await prepared(hass, flow_timeout_seconds=5, sample_wait_timeout_seconds=10)
    hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
    await start_native(hass, entry)
    try:
        async with asyncio.timeout(6):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert entry.runtime_data.control.fault == "flow_timeout"
        assert not any(output.is_on for output in hass.data["p3_fixture"]["outputs"])
    finally:
        await toggle(hass, entry, "flow_run", False)


@pytest.mark.parametrize("index", [0, 1])
async def test_restart_checks_nutrient_and_circulation_without_refill(dosing_hass, index):
    hass = dosing_hass
    entry = await prepared(hass)
    output = hass.data["p3_fixture"]["outputs"][index]
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": output.entity_id}, blocking=True
    )
    hass.data["p3_fixture"]["calls"].clear()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.control.fault == "restart_output_not_off"
    assert not entry.runtime_data.control.master
    assert not entry.runtime_data.control.running
    assert not hass.data["p3_fixture"]["calls"], "Restart does not seize externally ON outputs"


async def test_native_nutrient_only_midpoint_stops_pump_before_pulse_then_mixes(dosing_hass):
    hass = dosing_hass
    entry = await add_tank(hass)
    values = nutrient_payload(hass)
    values.pop("refill_output")
    values.update(
        commissioned=False,
        feedback_timeout=1,
        device_max_on_seconds=3,
        pulse_seconds=2,
        post_mix_seconds=1,
        sample_wait_timeout_seconds=5,
        stable_samples=1,
        stable_interval_seconds=1,
        flow_timeout_seconds=15,
    )
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(flow["flow_id"], values)
    await hass.async_block_till_done()
    assert entry.options["control"]["nutrient_commissioned"] is True
    assert not entry.options["control"].get("binding"), "This is a nutrient-only tank"
    hass.states.async_set("sensor.ec", "0.7", {"unit_of_measurement": "mS/cm"})
    pump, circulation = hass.data["p3_fixture"]["outputs"]
    # This native action is the first currently missing user-operable behavior.
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, "nutrient_enabled")
    assert not hass.data["p3_fixture"]["calls"], "Enable must not actuate"
    request = asyncio.create_task(
        hass.services.async_call(
            "uninus_nutriculture",
            "start_flow",
            {"config_entry_id": entry.entry_id},
            blocking=True,
            return_response=True,
        )
    )
    try:
        await asyncio.wait_for(pump.entered_on.wait(), 3)
        receipt = await asyncio.wait_for(request, 3)
        assert receipt["accepted"] is True and receipt["run_id"]
        assert circulation.is_on
        status = hass.states.get(target(hass, entry, "sensor", "control_status"))
        assert status.attributes["stage_states"]["refill"] == "skipped_disabled"
        assert status.attributes["stage_states"]["nutrient"] == "running"
        assert hass.data["p3_fixture"]["calls"][:2] == [("circulation", "on"), ("nutrient", "on")]
        hass.states.async_set("sensor.ec", "0.85", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(pump.entered_off.wait(), 0.75)
        assert not pump.is_on and circulation.is_on, "Required mixing outlives dosing"
        assert ("nutrient", "device_local_cutoff") not in hass.data["p3_fixture"]["calls"]
        async with asyncio.timeout(4):
            while entry.runtime_data.control.flow_state not in ("waiting_sample", "stabilizing"):
                await asyncio.sleep(0.01)
        hass.states.async_set("sensor.ec", "0.86", {"unit_of_measurement": "mS/cm"})
        await asyncio.wait_for(circulation.entered_off.wait(), 3)
        async with asyncio.timeout(2):
            while entry.runtime_data.control.running:
                await asyncio.sleep(0.01)
        assert entry.runtime_data.control.flow_state == "completed"
        assert entry.runtime_data.control.fault is None
        status = hass.states.get(target(hass, entry, "sensor", "control_status"))
        assert status.attributes["ready_for_irrigation"] is False
    finally:
        if not request.done():
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)
        await toggle(hass, entry, "flow_run", False)
