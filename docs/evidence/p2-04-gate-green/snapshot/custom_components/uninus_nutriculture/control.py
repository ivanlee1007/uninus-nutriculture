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
            from homeassistant.util import dt as dt_util
            from .control_settings import DAYS
            config = self.tank.entry.options.get("control", {})
            if not config.get("commissioned"):
                raise ServiceValidationError("uncommissioned")
            self.target = resolve(self.hass, config.get("binding"))
            if self.tank.snapshot()[0] == "invalid":
                raise ServiceValidationError("source_invalid")
            if float(self.hass.states.get(self.tank.sources["level"]).state) >= self.tank.parameters["level_low"]:
                raise ServiceValidationError("level_not_low")
            output = self.hass.states.get(self.target)
            if output is None or output.state != "off":
                raise ServiceValidationError("output_not_off")
            if DAYS[dt_util.now().weekday()] not in config.get("allowed_weekdays", {}).get("refill", DAYS):
                raise ServiceValidationError("weekday")
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
