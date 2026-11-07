async def drive(hass, entry, acid, snap, start_native, until, snapshot, asyncio):
    hass.states.async_set("sensor.level", ".2", {"unit_of_measurement": "m"})
    hass.states.async_set("sensor.ec", ".7", {"unit_of_measurement": "mS/cm"})
    hass.states.async_set("sensor.ph", "6.5", {"sample": 1})
    await hass.async_block_till_done()
    await start_native(hass, entry)
    c = entry.runtime_data.control
    pump, circ = hass.data["p3_fixture"]["outputs"]
    refill = hass.data["p2_fixture"]["hardware"]
    await until(lambda: refill.is_on)
    hass.states.async_set("sensor.level", "1.0", {"unit_of_measurement": "m"})
    await asyncio.wait_for(circ.entered_on.wait(), 3)
    assert refill.is_on and circ.is_on
    _overlap = snap()
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
    for _ in range(10):
        await asyncio.sleep(0)
    status = snapshot(hass, entry)
    attr = status["states"][status["status_id"]]["attributes"]
    assert attr["flow_state"] == "completed" and all(
        r["result"] == "completed" for r in attr["step_runtime"].values()
    )
    assert all(v == "off" for v in attr["output_states"].values())
    assert not c.leases
    assert not c.flow.pending
    owners = (c.flow.refill, c.nutrient_stage, c.acid_stage, c.mix_stage)
    assert all(not owner.owns_io for owner in owners)
    assert all(task.done() for owner in owners for task in owner.operations.values())
    return status
