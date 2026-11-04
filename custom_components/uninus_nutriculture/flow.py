"""Four unique rows; one entry-owned coordinator, no scheduler or generic DAG."""

import asyncio
import time
import uuid
from copy import deepcopy

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .control_auth import authorize
from .control_settings import DAYS, STAGES, resolve
from .flow_settings import source, validate_plan


def record():
    return dict(phase=None, result=None, started_at=None, settled_at=None, waiting_reason=None)


class RefillStep:
    """Refill's isolated ownership, with Controller retaining physical dispatch."""

    def __init__(self, flow):
        self.flow = flow
        self.control = flow.control
        self.task = None
        self.operations = {}
        self.owns_io = False
        self.result = None
        self.phase = None
        self.cleaning = False
        self.revoked = None
        self.cleanup_lock = asyncio.Lock()

    async def start(self):
        c = self.control
        self.binding = deepcopy(c.tank.entry.options["control"]["binding"])
        self.target = resolve(c.hass, self.binding)
        state = c.hass.states.get(self.target)
        if not state or state.state != "off":
            raise ServiceValidationError("output_not_off")
        self.started = time.monotonic()
        self.high = self.flow.params["level_high"]
        self.deadline = self.started + self.flow.params["refill_timeout"] * 60
        self.cleaning = False
        self.operations = {}
        self.result = None
        self.revoked = None
        self.owns_io = True
        self.task = c.tank.entry.async_create_background_task(
            c.hass, self.run(), "flow refill", eager_start=False
        )

    def changed(self, event):
        if event.data.get("entity_id") in self.control.tank.sources.values():
            key = next(
                k for k, v in self.control.tank.sources.items() if v == event.data["entity_id"]
            )
            # Inspect the event's captured value, never a later restored repaint.
            state = event.data.get("new_state")
            try:
                import math

                if (
                    state is None
                    or not math.isfinite(float(state.state))
                    or state.attributes.get("unit_of_measurement")
                    not in {"level": ("m",), "ec": ("mS/cm",), "ph": (None, "", "pH")}[key]
                ):
                    self.revoked = "source_invalid"
            except ValueError, TypeError:
                self.revoked = "source_invalid"
        if (
            not self.cleaning
            and self.phase == "refilling"
            and event.data.get("entity_id") == self.target
        ):
            state = event.data.get("new_state")
            if state is None or state.state != "on":
                self.revoked = "output_unexpected"

    async def output(self, enabled):
        c = self.control
        task = c.hass.async_create_background_task(
            c.flow_refill_dispatch(self, enabled), "flow refill output", eager_start=False
        )
        self.operations[enabled] = task

        def settled(t):
            if not t.cancelled():
                t.exception()
            if enabled and self.cleaning:
                c.hass.async_create_background_task(
                    self.cleanup("fault"), "late refill closure", eager_start=False
                )

        task.add_done_callback(settled)
        async with asyncio.timeout(c.tank.entry.options["control"].get("feedback_timeout", 10)):
            await asyncio.shield(task)
            while (s := c.hass.states.get(self.target)) is None or s.state != (
                "on" if enabled else "off"
            ):
                await asyncio.sleep(0.01)

    async def run(self):
        result = "completed"
        try:
            self.phase = "starting"
            await self.output(True)
            self.phase = "refilling"
            while True:
                self.high = min(self.high, self.control.tank.parameters["level_high"])
                self.deadline = min(
                    self.deadline,
                    self.started + self.control.tank.parameters["refill_timeout"] * 60,
                )
                if self.revoked:
                    raise ServiceValidationError(self.revoked)
                if any(source(self.control.tank, k) is None for k in ("level", "ph", "ec")):
                    raise ServiceValidationError("source_invalid")
                if time.monotonic() >= self.deadline:
                    raise ServiceValidationError("refill_timeout")
                if source(self.control.tank, "level") >= self.high:
                    break
                self.control.tank.publish()
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            result = "aborted"
        except Exception as err:
            from .control import _fault_code

            self.control.fault = self.revoked or _fault_code(str(err))
            result = "fault"
        finally:
            await asyncio.shield(self.cleanup(result))

    async def cleanup(self, result):
        async with self.cleanup_lock:
            self.cleaning = True
            self.phase = "stopping"
            try:
                await self.output(False)
                self.owns_io = any(not t.done() for t in self.operations.values())
                if not self.owns_io:
                    self.result = "fault" if self.control.fault else result
                    self.phase = None
            except Exception:
                if self.control.fault != "emergency_stop":
                    self.control.fault = "stop_unconfirmed"
                self.owns_io = True
            self.control.tank.publish()

    async def stop(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.owns_io:
            await self.cleanup("aborted")


class FlowCoordinator:
    def __init__(self, control):
        self.control = control
        self.tank = control.tank
        self.task = None
        self.active = False
        self.stopping = False
        self.run_plan = None
        self.records = {s: record() for s in STAGES}
        self.times = {}
        self.refill = RefillStep(self)
        self.outcome = None
        self.clock = time.monotonic
        self.weekday = lambda: DAYS[dt_util.now().weekday()]
        self.circ_lock = asyncio.Lock()
        self.circ_start = None
        self.circ_cutoff = None
        self.required_sources = {}

    def validate_sources(self, name):
        if any(source(self.tank, key) is None for key in self.required_sources.get(name, ())):
            raise ServiceValidationError("source_invalid")

    def changed(self, name, event):
        from .flow_settings import source_state

        for key in self.required_sources.get(name, ()):
            if (
                event.data.get("entity_id") == self.tank.sources[key]
                and source_state(self.tank, key, event.data.get("new_state")) is None
            ):
                self.stage(name).revoked = "source_invalid"

    def reset_closed_stages(self):
        """Renew per-run deadlines only after all physical responsibility closed."""
        c = self.control
        stages = [self.stage(s) for s in STAGES]
        if c.leases or self.circ_start is not None or self.circ_cutoff is not None:
            raise ServiceValidationError("busy")
        for stage in stages:
            if stage.owns_io or any(not task.done() for task in stage.operations.values()):
                raise ServiceValidationError("busy")
            for binding in getattr(stage, "bindings", {}).values():
                state = c.hass.states.get(resolve(c.hass, binding))
                if state is None or state.state != "off":
                    raise ServiceValidationError("output_not_off")
        for stage in stages:
            for field in ("circ_physical_cutoff", "circ_dispatch_at"):
                if hasattr(stage, field):
                    delattr(stage, field)

    def tighten(self):
        if not self.active:
            return
        minimum = {
            "pulse_seconds",
            "max_total_on_seconds",
            "max_pulses",
            "flow_timeout_seconds",
            "sample_wait_timeout_seconds",
            "ec_danger_high",
        }
        maximum = {
            "safe_min_level_m",
            "ph_danger_low",
            "post_mix_seconds",
            "stable_samples",
            "stable_interval_seconds",
        }
        for namespace, values in self.bounds.items():
            live = self.tank.entry.options.get(namespace, {})
            for key, value in list(values.items()):
                if key in live and key in minimum:
                    values[key] = min(value, live[key])
                elif key in live and key in maximum:
                    values[key] = max(value, live[key])
        for key in ("refill_timeout", "ph_timeout", "ec_timeout", "mix_duration", "level_high"):
            self.params[key] = min(self.params[key], self.tank.parameters[key])
        from decimal import Decimal

        for role, measurement, direction in (("nutrient", "ec", 1), ("acid", "ph", -1)):
            value = float(
                direction
                * (
                    Decimal(str(self.tank.parameters[measurement + "_low"]))
                    + Decimal(str(self.tank.parameters[measurement + "_high"]))
                )
                / 2
            )
            original = float(
                direction
                * (
                    Decimal(str(self.params[measurement + "_low"]))
                    + Decimal(str(self.params[measurement + "_high"]))
                )
                / 2
            )
            self.midpoints[role] = min(self.midpoints.get(role, original), value)

    def settings(self, role):
        return deepcopy(
            self.bounds["dosing_parameters"]
            if role == "nutrient"
            else {**self.bounds["acid_parameters"], **self.bounds["safety_parameters"]}
            if role == "acid"
            else self.bounds["mix_parameters"]
        )

    def stage(self, s):
        return self.refill if s == "refill" else getattr(self.control, s + "_stage")

    @property
    def pending(self):
        return self.active or self.refill.owns_io

    def refresh(self):
        if not self.run_plan:
            return
        for name, r in self.records.items():
            stage = self.stage(name)
            if name in self.times and stage.owns_io:
                r["phase"] = stage.phase or "starting"
                r["waiting_reason"] = None
            elif name in self.times and stage.result and not r["result"]:
                self.settle(name, stage.result)

    @property
    def state(self):
        self.refresh()
        if self.control.fault:
            return "fault"
        if self.stopping:
            return "stopping"
        if not self.active:
            return self.outcome or ("idle" if self.control.master else "disabled")
        phases = [r["phase"] for r in self.records.values() if not r["result"]]
        if any(
            p not in (None, "waiting_delay", "waiting_condition", "waiting_resource")
            for p in phases
        ):
            return "running"
        return (
            "waiting_condition"
            if any(p in ("waiting_condition", "waiting_resource") for p in phases)
            else "waiting_delay"
        )

    def settle(self, name, result):
        r = self.records[name]
        r.update(
            phase=None, result=result, settled_at=dt_util.utcnow().isoformat(), waiting_reason=None
        )
        self.settled[name] = self.clock()

    def wait(self, name, phase, reason):
        self.records[name].update(phase=phase, waiting_reason=reason)

    async def start(self, context, guard=None, request_id=None, service=False):
        c = self.control
        requested_generation = c.generation
        await authorize(c.hass, context)
        async with self.tank.lock:
            await authorize(c.hass, context)
            async with c.lock:
                if guard:
                    guard()
                if requested_generation != c.generation:
                    raise ServiceValidationError("revoked")
                if not self.tank.active or not c.master or c.fault:
                    raise ServiceValidationError("disabled")
                if request_id in c.receipts:
                    return dict(c.receipts[request_id][1])
                if c.running:
                    if service:
                        raise ServiceValidationError("busy")
                    return dict(accepted=True, run_id=c.run_id)
                o = self.tank.entry.options
                p, d = validate_plan(o["flow_plan"], o["control"]["allowed_weekdays"])
                enabled = {s: bool(getattr(c, s)) for s in STAGES}
                if not any(enabled.values()):
                    raise ServiceValidationError("disabled")
                for s in STAGES:
                    if enabled[s] and not o["control"].get(
                        "commissioned" if s == "refill" else s + "_commissioned"
                    ):
                        raise ServiceValidationError("uncommissioned")
                self.reset_closed_stages()
                c.run_id = uuid.uuid4().hex
                c.run_context = context
                c.stop_context = None
                self.generation = c.generation
                self.bounds = deepcopy(
                    {
                        k: o.get(k, {})
                        for k in (
                            "dosing_parameters",
                            "acid_parameters",
                            "mix_parameters",
                            "safety_parameters",
                        )
                    }
                )
                self.params = dict(self.tank.parameters)
                self.midpoints = {}
                self.run_plan = deepcopy(
                    dict(
                        run_id=c.run_id,
                        settings_revision=o.get("settings_revision", 0),
                        flow_plan_revision=o.get("flow_plan_revision", 0),
                        flow_plan=p,
                        allowed_weekdays=d,
                        enabled_stages=enabled,
                    )
                )
                self.records = {s: record() for s in STAGES}
                self.times = {}
                self.settled = {}
                self.required_sources = {}
                self.accepted = self.clock()
                self.deadline = self.accepted + p["run_timeout_seconds"]
                self.active = True
                self.stopping = False
                self.outcome = None
                self.circ_start = self.circ_cutoff = None
                for s in STAGES:
                    self.stage(s).result = None
                self.task = self.tank.entry.async_create_background_task(
                    c.hass, self.run(), "four-stage flow", eager_start=False
                )
                result = dict(accepted=True, run_id=c.run_id)
                if request_id:
                    c.receipts[request_id] = (time.monotonic(), dict(result))
                while len(c.receipts) > 64:
                    c.receipts.pop(next(iter(c.receipts)))
                self.tighten()
                self.tank.publish()
                return result

    def anchor(self, row, index):
        rule = row["start_rule"]
        if rule == "flow_start":
            return self.accepted
        previous = self.run_plan["flow_plan"]["rows"][index - 1]["stage"]
        r = self.records[previous]
        from .flow_settings import dependency_ready

        ready = dependency_ready(rule, r["result"], r["started_at"] is not None)
        if ready is not True:
            return ready
        return self.times[previous] if rule == "after_previous_started" else self.settled[previous]

    async def admit(self, row):
        name = row["stage"]
        c = self.control
        async with c.lock:
            await authorize(c.hass, c.run_context)
            if self.generation != c.generation or not c.master or c.fault or self.stopping:
                raise ServiceValidationError("revoked")
            if not self.run_plan["enabled_stages"][name] or not getattr(c, name):
                self.settle(name, "skipped_disabled")
                return True
            required = ["level"] if name == "mix" else ["level", "ph", "ec"]
            if row["condition"]:
                required.append(row["condition"]["source"])
            if any(source(self.tank, k) is None for k in required):
                raise ServiceValidationError("source_invalid")
            condition = row["condition"]
            if condition and not (
                source(self.tank, condition["source"]) >= condition["value"]
                if condition["operator"] == "gte"
                else source(self.tank, condition["source"]) <= condition["value"]
            ):
                self.wait(name, "waiting_condition", "condition_not_met")
                return False
            if name in ("refill", "nutrient", "acid") and any(
                self.stage(s).owns_io for s in ("refill", "nutrient", "acid") if s != name
            ):
                self.wait(name, "waiting_resource", "resource_chemical")
                return False
            if name != "refill":
                minimum = self.settings(name)["safe_min_level_m"]
                low = source(self.tank, "level") < minimum or (
                    name == "nutrient" and source(self.tank, "level") == minimum
                )
                if low:
                    from .flow_settings import reachable_refill

                    if self.refill.owns_io or reachable_refill(
                        self.tank,
                        self.run_plan["flow_plan"],
                        self.run_plan["allowed_weekdays"],
                        self.weekday(),
                        {
                            s: self.run_plan["enabled_stages"][s] and bool(getattr(c, s))
                            for s in STAGES
                        },
                        self.records,
                        {name},
                    ):
                        self.wait(name, "waiting_condition", "level_unsafe")
                        return False
                    raise ServiceValidationError("level_unsafe")
            elif source(self.tank, "level") >= self.tank.parameters["level_low"]:
                self.settle(name, "completed")
                return True
            if self.weekday() not in self.run_plan["allowed_weekdays"][name]:
                self.settle(name, "skipped_weekday")
                return True
            stage = self.stage(name)
            self.required_sources[name] = frozenset(required)
            if name == "refill":
                await stage.start()
            else:
                await stage.start(c.run_context, None)
            self.times[name] = self.clock()
            self.records[name].update(phase="starting", waiting_reason=None)
            return True

    def dispatched(self, name):
        r = self.records[name]
        if r["started_at"] is None:
            r["started_at"] = dt_util.utcnow().isoformat()
            self.times[name] = self.clock()

    async def run(self):
        try:
            while True:
                if self.generation != self.control.generation or self.stopping:
                    raise asyncio.CancelledError
                if self.control.fault:
                    raise ServiceValidationError("revoked")
                if self.clock() >= self.deadline:
                    raise ServiceValidationError("flow_timeout")
                for name in STAGES:
                    stage = self.stage(name)
                    if stage.owns_io:
                        if stage.revoked:
                            raise ServiceValidationError(stage.revoked)
                        self.validate_sources(name)
                self.refresh()
                for i, row in enumerate(self.run_plan["flow_plan"]["rows"]):
                    name = row["stage"]
                    r = self.records[name]
                    if r["result"] or name in self.times:
                        continue
                    anchor = self.anchor(row, i)
                    if anchor is False:
                        self.settle(name, "blocked_dependency")
                        continue
                    if anchor is None:
                        self.wait(name, "waiting_condition", "dependency_not_started")
                        continue
                    due = anchor + row["delay_seconds"]
                    if self.clock() < due:
                        self.wait(name, "waiting_delay", "delay_pending")
                        continue
                    if self.clock() >= min(self.deadline, due + row["wait_timeout_seconds"]):
                        raise ServiceValidationError("flow_timeout")
                    await self.admit(row)
                self.refresh()
                if all(r["result"] for r in self.records.values()):
                    self.outcome = "completed"
                    break
                self.tank.publish()
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            self.outcome = "aborted"
        except Exception as err:
            from .control import _fault_code

            self.control.fault = self.control.fault or _fault_code(str(err))
            self.outcome = "fault"
        finally:
            if self.outcome != "completed":
                self.stopping = True
                await asyncio.shield(self.close_owners())
                for s, r in self.records.items():
                    if not r["result"] and not self.stage(s).owns_io:
                        self.settle(s, "fault" if self.control.fault else "aborted")
            self.active = False
            self.stopping = False
            self.tank.publish()

    async def close_owners(self):
        await asyncio.gather(*(self.stage(s).stop() for s in STAGES if self.stage(s).owns_io))

    async def stop(self):
        self.stopping = True
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        await self.close_owners()
        self.active = False
        self.stopping = False
        if self.run_plan and not self.outcome:
            self.outcome = "aborted"
        self.tank.publish()
