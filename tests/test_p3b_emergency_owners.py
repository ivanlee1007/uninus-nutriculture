"""Native commissioned owners must all close, irrespective of selected role."""

import asyncio

import pytest
from homeassistant.core import Context
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from p3_fixtures import nutrient_payload
from test_p2_control import add_tank, target, toggle
from test_p3_dosing import dosing_hass as dosing_hass
from test_p3_dosing import start_native
from test_p3b_native import acid_values


@pytest.mark.parametrize(
    "active,held", [("acid", "acid"), ("acid", "circulation"), ("mix", "nutrient")]
)
async def test_commissioned_emergency_independent_owners(dosing_hass, active, held):
    hass = dosing_hass
    nutrient, circ = hass.data["p3_fixture"]["outputs"]
    acid = type(nutrient)("acid_emergency")
    foreign = type(nutrient)("foreign_emergency")
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
    assert result["type"] == FlowResultType.CREATE_ENTRY, result
    c = entry.runtime_data.control
    assert c.supports_nutrient and c.supports_acid and c.supports_mix
    assert entry.options["control"]["commissioned"]
    known = {"nutrient": nutrient, "acid": acid, "circulation": circ, "refill": refill}
    assert len({er.async_get(hass).async_get(out.entity_id).id for out in known.values()}) == 4
    hass.states.async_set("sensor.ph", "6.5", {"sample": 2})
    await toggle(hass, entry, "automation_enabled")
    await toggle(hass, entry, active + "_enabled")
    assert sum((c.nutrient, c.acid, c.mix, c.refill)) == 1
    await start_native(hass, entry)
    await asyncio.wait_for((acid if active == "acid" else circ).entered_on.wait(), 2)
    for out in (nutrient, refill, foreign) + ((acid,) if active == "mix" else ()):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": out.entity_id}, blocking=True
        )
    gate = asyncio.Event()
    known[held].off_ack_gate = gate
    origin = Context()
    task = asyncio.create_task(
        hass.services.async_call(
            "button",
            "press",
            {"entity_id": target(hass, entry, "button", "emergency_stop")},
            blocking=True,
            context=origin,
        )
    )
    try:
        await asyncio.wait_for(acid.entered_off.wait(), 0.7)
        await asyncio.wait_for(circ.entered_off.wait(), 0.7)
        await asyncio.sleep(0.08)
        assert foreign.is_on and not foreign.entered_off.is_set()
        assert not refill.is_on and not acid.is_on and not circ.is_on
        assert c.running and not task.done(), "Held OFF must retain aggregate pending truth"
        assert nutrient.entered_off.is_set() and not nutrient.is_on, (
            "Commissioned idle N externally ON was not closed during emergency"
        )
        stages = {"nutrient": c.nutrient_stage, "acid": c.acid_stage, "mix": c.mix_stage}
        for role, stage in stages.items():
            pending = [op for op in stage.operations.values() if not op.done()]
            expected = held == "circulation" or held == role
            assert bool(pending) == expected, (role, held, stage.operations)
            assert stage.owns_io == expected, (role, held, stage.owns_io)
        for role in ("nutrient", "acid", "circulation"):
            contexts = [
                ctx
                for name, action, ctx in hass.data["p3_fixture"]["contexts"]
                if name == known[role].role and action == "off"
            ]
            assert contexts and all(
                ctx.user_id is None and ctx.parent_id == origin.id for ctx in contexts
            )
        assert all(not out.is_on for out in known.values())
    finally:
        gate.set()
        await asyncio.wait_for(task, 4)
        # Explicit fixture teardown is never used as emergency success evidence.
        for out in (nutrient, acid, foreign):
            await hass.services.async_call(
                "switch", "turn_off", {"entity_id": out.entity_id}, blocking=True
            )
        await toggle(hass, entry, "flow_run", False)
    assert not c.running
    assert not any(stage.owns_io for stage in stages.values())
