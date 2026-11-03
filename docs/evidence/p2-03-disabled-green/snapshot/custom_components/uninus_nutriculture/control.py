"""Entry-owned refill execution; no scheduling or dosing."""
import asyncio
import uuid

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback

from .control_settings import resolve


class Controller:
    def __init__(self, tank):
        self.tank = tank
        self.hass = tank.hass
        self.master = False
        self.refill = False
        self.running = False
        self.flow_state = "uncommissioned"
        self.fault = None
        self.run_id = None
        self.lock = asyncio.Lock()
        self.target = None
        self.unsub = self.hass.bus.async_listen(EVENT_STATE_CHANGED, self.changed)

    @callback
    def changed(self, event):
        if self.running and event.data.get("entity_id") in self.tank.sources.values():
            self.hass.async_create_task(self.evaluate())

    async def evaluate(self):
        if self.running and float(self.hass.states.get(self.tank.sources["level"]).state) >= self.tank.parameters["level_high"]:
            await self.stop("completed")

    async def action(self, key, enabled, context):
        if key == "automation_enabled":
            self.master = enabled
        elif key == "refill_enabled":
            self.refill = enabled
        elif key == "flow_run":
            if enabled:
                return await self.start(context)
            await self.stop()
        self.tank.publish()

    async def start(self, context):
        from homeassistant.exceptions import ServiceValidationError
        async with self.lock:
            if not self.master or not self.refill:
                raise ServiceValidationError("disabled")
            if self.running:
                return
            self.target = resolve(self.hass, self.tank.entry.options["control"]["binding"])
            self.run_id = uuid.uuid4().hex
            self.running = True
            self.flow_state = "refilling"
            await self.hass.services.async_call("switch", "turn_on", {"entity_id": self.target}, blocking=True, context=context)
            self.tank.publish()

    async def stop(self, state="aborted"):
        async with self.lock:
            if self.running:
                await self.hass.services.async_call("switch", "turn_off", {"entity_id": self.target}, blocking=True)
                self.running = False
                self.flow_state = state
                self.tank.publish()
