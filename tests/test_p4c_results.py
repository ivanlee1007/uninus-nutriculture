"""Registered Core result tracer; fake equipment only, no fake coordinators."""

import asyncio
from copy import deepcopy

import pytest
from homeassistant.core import SupportsResponse, callback
from homeassistant.helpers import entity_registry as er
from test_p2_control import toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3c_flow import prepared, save_v5, until

DOMAIN = "uninus_nutriculture"


async def read(h, e):
    return await h.services.async_call(
        DOMAIN,
        "get_result_v1",
        {"config_entry_id": e.entry_id},
        blocking=True,
        return_response=True,
    )


@pytest.mark.parametrize("entrance", ["service", "switch"])
async def test_registered_result_admission_terminal_sensor_cache(dosing_hass, entrance):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    # Transport-only baseline shim: missing native state is business RED.
    if not h.services.has_service(DOMAIN, "get_result_v1"):

        async def noop(call):
            return {}

        h.services.async_register(
            DOMAIN, "get_result_v1", noop, supports_response=SupportsResponse.ONLY
        )
    events = []

    @callback
    def observed(event):
        events.append(deepcopy(dict(event.data)))

    unsub = h.bus.async_listen(DOMAIN + "_result_v1", observed)
    h.states.async_set("sensor.level", "2.4", {"unit_of_measurement": "m"})
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "refill_enabled")
    if entrance == "service":
        accepted = await start_native(h, e)
        assert accepted["accepted"] is True
    else:
        await toggle(h, e, "flow_run")
    await until(lambda: not e.runtime_data.control.running)
    await h.async_block_till_done()
    registry = er.async_get(h)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, e.entry_id + ":result_status")
    assert entity_id is not None, "accepted run has no native result projection"
    dto = await read(h, e)
    assert dto["current_run"] is None and dto["last_result"]["state"] == "completed"
    assert dto["last_result"]["closure"] == "confirmed"
    assert dto["last_result"]["started_at"] is None  # refill already sufficient
    assert dto["last_result"]["run_id"] == e.runtime_data.control.run_id
    assert h.states.get(entity_id).state == "completed"
    attrs = dict(h.states.get(entity_id).attributes)
    attrs.pop("friendly_name", None)
    assert attrs == dto
    assert [ev["kind"] for ev in events] == ["accepted", "completed"]
    assert events[-1]["run"] == dto["last_result"]
    frozen = deepcopy(dto)
    for _ in range(100):
        assert await read(h, e) == frozen
    assert len(events) == 2
    assert e.runtime_data.control.fault is None
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
    unsub()


async def test_idle_danger_edges_readonly_no_actuation(dosing_hass):
    h = dosing_hass
    e, _ = await prepared(h)
    await save_v5(h, e)
    c = e.runtime_data.control
    before = (c.master, c.fault, dict(e.options))
    events = []

    @callback
    def seen(ev):
        events.append(dict(ev.data))

    unsub = h.bus.async_listen(DOMAIN + "_result_v1", seen)
    h.states.async_set("sensor.ph", "3.7", {"unit_of_measurement": "pH"})
    h.states.async_set("sensor.ec", "1.4", {"unit_of_measurement": "mS/cm"})
    await h.async_block_till_done()
    assert {ev["kind"] for ev in events} == {"ph_low", "ec_high"}
    assert all(ev["run"] is None for ev in events)
    for _ in range(10):
        e.runtime_data.publish()
    await h.async_block_till_done()
    assert len(events) == 2
    assert (c.master, c.fault, dict(e.options)) == before
    assert not h.data["p2_fixture"]["calls"] and not h.data["p3_fixture"]["calls"]
    unsub()


async def test_pending_on_off_ack_not_terminal_until_true_closure(dosing_hass):
    from test_p3c_flow import plan

    h = dosing_hass
    e, _ = await prepared(h)
    p = plan()
    for row in p["rows"]:
        row.update(start_rule="flow_start", delay_seconds=0)
    await save_v5(h, e, p)
    h.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await toggle(h, e, "automation_enabled")
    await toggle(h, e, "nutrient_enabled")
    pump, circ = h.data["p3_fixture"]["outputs"]
    pump.on_ack_gate = asyncio.Event()
    await start_native(h, e)
    await asyncio.wait_for(pump.entered_on.wait(), 3)
    request = asyncio.create_task(toggle(h, e, "flow_run", False))
    await asyncio.wait_for(pump.entered_off.wait(), 1)
    dto = await read(h, e)
    assert dto["last_result"] is None and dto["current_run"] is not None
    assert not pump.is_on and not pump.on_ack_gate.is_set()
    pump.on_ack_gate.set()
    await request
    await until(lambda: e.runtime_data.results.dto()["last_result"] is not None)
    dto = await read(h, e)
    assert dto["last_result"]["state"] != "completed"
    assert dto["last_result"]["closure"] == "confirmed"
    assert not pump.is_on and not circ.is_on and not e.runtime_data.control.leases
