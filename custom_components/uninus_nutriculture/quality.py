"""Ephemeral per-entry authority; no actuator service calls."""

import math
from datetime import datetime, timedelta
from uuid import uuid4

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED, EVENT_STATE_REPORTED
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .control_settings import resolve
from .quality_settings import STAGES, read


class QualityCoordinator:
    def __init__(self, tank):
        self.tank = tank
        self.epoch = uuid4().hex
        self.observation_revision = 0
        self.clock = tank.hass.loop.time
        # One ephemeral UTC/monotonic pair per coordinator. Projection never
        # resamples wall time on reads; all actual expiry checks remain monotonic.
        self._projection_utc = dt_util.utcnow()
        self._projection_monotonic = self.clock()
        self.closed = False
        self.timer = None
        self.tokens = {}
        self.samples = {}
        self.used = {}
        self.regressed = set()
        self.count = 0
        self.first = None
        self.last = None
        self.since = None
        self.seen = None
        self.candidate = None
        self.consumed = True
        self.granted = False
        self.hard = None
        self.generation = None
        self.reasons = ["no_current_run"]
        self.completion = dict(state="none", run_id=None, settled_at=None)
        self.fingerprint = self.settings()
        self.output_registry_targets = {}
        self.owned_registry_targets = {}
        self.remember_registry_targets()
        self.unsubs = [
            tank.hass.bus.async_listen(EVENT_STATE_CHANGED, self.changed),
            tank.hass.bus.async_listen(
                EVENT_STATE_REPORTED, self.changed, event_filter=self.filtered
            ),
            tank.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self.registry),
            tank.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.close),
        ]
        tank.entry.async_on_unload(self.close)

    def settings(self):
        return {
            k: v
            for k, v in self.tank.entry.options.items()
            if k not in ("recipe_catalog", "quality_policy")
        }

    def reset(self):
        self.count = 0
        self.first = self.last = self.since = None
        self.used = dict(self.tokens)

    def invalidate(self, reason):
        corrective = (
            self.candidate is None
            and self.completion["state"] == "running"
            and reason
            in (
                "source_invalid",
                "source_stale",
                "sample_unconfirmed",
                "out_of_range",
                "sample_regressed",
            )
        )
        self.granted = False
        self.candidate = None
        self.consumed = self.consumed if corrective else True
        self.hard = None
        self.reasons = [reason]
        self.reset()
        self.observation_revision += 1
        self.schedule()

    def notify(self):
        for listener in tuple(self.tank.listeners):
            owner = getattr(listener, "__self__", None)
            if getattr(owner, "tank", None) is self.tank and hasattr(owner, "async_write_ha_state"):
                listener()

    @callback
    def filtered(self, event):
        return event.get("entity_id") in self.tank.sources.values()

    @callback
    def registry(self, event):
        if self.closed:
            return
        identity = event.data.get("entity_id")
        row = er.async_get(self.tank.hass).async_get(identity) if identity else None
        previous = event.data.get("changes", {}).get("entity_id")
        # Resolve relevance from configured/captured identities, never run/closure state.
        self.remember_registry_targets()
        targets = {
            *self.tank.sources.values(),
            *self.output_registry_targets.values(),
            *self.owned_registry_targets.values(),
        }
        if (
            identity in targets
            or (previous is not None and previous in targets)
            or (row and row.config_entry_id == self.tank.entry.entry_id)
        ):
            self.epoch = uuid4().hex
            self.invalidate("capability_lost")
            self.notify()
        if event.data.get("action") == "remove":
            self.owned_registry_targets = {
                key: value
                for key, value in self.owned_registry_targets.items()
                if value != identity
            }

    def remember_registry_targets(self):
        control = self.tank.entry.options.get("control", {})
        bindings = {
            binding.get("registry_id")
            for key in ("binding", "nutrient_binding", "acid_binding", "circulation_binding")
            if (binding := control.get(key))
        }
        # Keep a bound output's last entity ID even after its registry row disappears.
        self.output_registry_targets = {
            key: value for key, value in self.output_registry_targets.items() if key in bindings
        }
        for row in er.async_get(self.tank.hass).entities.values():
            if row.id in bindings:
                self.output_registry_targets[row.id] = row.entity_id
            if row.config_entry_id == self.tank.entry.entry_id:
                self.owned_registry_targets[row.id] = row.entity_id

    def sample(self, key, state, p):
        if state is None:
            raise ValueError("source_invalid")
        row = er.async_get(self.tank.hass).async_get(state.entity_id)
        if row and row.disabled_by:
            raise ValueError("source_invalid")
        value = float(state.state)
        if (
            not math.isfinite(value)
            or state.attributes.get("unit_of_measurement")
            not in {"ph": (None, "", "pH"), "ec": ("mS/cm",), "level": ("m",)}[key]
        ):
            raise ValueError("source_invalid")
        age = (dt_util.utcnow() - state.last_reported).total_seconds()
        maximum = self.tank.entry.options.get(
            "max_age_seconds", self.tank.entry.data.get("max_age_seconds", 300)
        )
        if not 0 <= age < maximum:
            raise ValueError("source_stale")
        r = p["sources"][key]
        if not r["report_contract_confirmed"]:
            raise ValueError("sample_unconfirmed")
        token = state.last_reported.timestamp()
        remaining = maximum - age
        if r["mode"] == "sequence":
            token = state.attributes.get(r["attribute"])
            if type(token) is not int or token < 0:
                raise ValueError("source_invalid")
        elif r["mode"] == "timestamp":
            try:
                stamp = datetime.fromisoformat(state.attributes.get(r["attribute"]))
                if stamp.tzinfo is None:
                    raise ValueError
                age2 = (dt_util.utcnow() - stamp).total_seconds()
            except ValueError, TypeError:
                raise ValueError("source_invalid") from None
            if not 0 <= age2 < maximum:
                raise ValueError("source_stale")
            token = stamp.timestamp()
            remaining = min(remaining, maximum - age2)
        return token, value, self.clock() + remaining

    def health(self, p):
        if self.regressed:
            return "sample_regressed"
        for k in ("ph", "ec", "level"):
            try:
                _, v, _ = self.sample(k, self.tank.hass.states.get(self.tank.sources[k]), p)
            except (ValueError, TypeError) as err:
                return (
                    str(err)
                    if str(err) in ("source_invalid", "source_stale", "sample_unconfirmed")
                    else "source_invalid"
                )
            if k in self.samples and self.clock() >= self.samples[k][1]:
                return "source_stale"
            if not self.tank.parameters[k + "_low"] <= v <= self.tank.parameters[k + "_high"]:
                return "out_of_range"
        return None

    def qualified(self, p):
        return (
            self.count >= p["stable_samples"]
            and self.first is not None
            and self.last - self.first >= p["stable_duration_seconds"]
        )

    @callback
    def changed(self, event):
        if self.closed:
            return
        eid = event.data.get("entity_id")
        if eid not in self.tank.sources.values():
            if self.candidate and (reason := self.guard()):
                self.invalidate(reason)
                self.notify()
            return
        k = next(k for k, v in self.tank.sources.items() if v == eid)
        try:
            p, _ = read(self.tank)
            token, v, deadline = self.sample(k, event.data.get("new_state"), p)
            old = self.tokens.get(k)
            if old is not None and token < old:
                self.regressed.add(k)
            if k in self.regressed:
                raise ValueError("sample_regressed")
            prev = event.data.get("old_state")
            if (
                p["sources"][k]["mode"] == "reported"
                and event.event_type == EVENT_STATE_CHANGED
                and prev
                and prev.state == event.data["new_state"].state
            ):
                return
            if old is not None and token == old:
                return
            self.tokens[k] = token
            self.samples[k] = (v, deadline)
            self.observation_revision += 1
            if not self.tank.parameters[k + "_low"] <= v <= self.tank.parameters[k + "_high"]:
                self.invalidate("out_of_range")
            else:
                self.observe()
                if (
                    p["enabled"]
                    and self.health(p) is None
                    and all(
                        k in self.tokens and self.tokens[k] != self.used.get(k)
                        for k in ("ph", "ec", "level")
                    )
                ):
                    now = self.clock()
                    if self.last is None or now - self.last >= p["stable_interval_seconds"]:
                        self.used = dict(self.tokens)
                        self.last = now
                        if self.first is None:
                            self.first = now
                            self.since = dt_util.utcnow().isoformat()
                        self.count = min(p["stable_samples"], self.count + 1)
                        if (
                            self.qualified(p)
                            and self.candidate
                            and not self.consumed
                            and not self.guard()
                        ):
                            if not self.granted:
                                self.hard = now + p["permit_ttl_seconds"]
                            self.granted = True
                            self.reasons = []
            self.schedule()
        except Exception as err:
            code = str(err)
            self.samples.pop(k, None)
            self.invalidate(
                code
                if code
                in ("source_invalid", "source_stale", "sample_unconfirmed", "sample_regressed")
                else "source_invalid"
            )
        self.notify()

    def guard(self):
        t = self.tank
        c = t.control
        if self.closed or not t.active or t.entry.disabled_by:
            return "entry_inactive"
        registry = er.async_get(t.hass)
        for domain, key in (("sensor", "quality_status"), ("binary_sensor", "irrigation_permit")):
            identity = registry.async_get_entity_id(domain, DOMAIN, f"{t.entry.entry_id}:{key}")
            row = registry.async_get(identity) if identity else None
            if (
                row is None
                or row.disabled_by
                or row.config_entry_id != t.entry.entry_id
                or t.hass.states.get(identity) is None
            ):
                return "capability_lost"
        if c.fault:
            return "fault"
        if not c.master:
            return "master_off"
        if self.seen and self.generation != c.generation:
            return "aborted"
        if (
            c.running
            or c.flow.stopping
            or c.leases
            or c.late_on
            or any(x is not None and not x.done() for x in (c.on_task, c.off_task))
        ):
            return "closure_pending"
        for s in STAGES:
            owner = c.flow.stage(s)
            if owner.owns_io or any(not task.done() for task in owner.operations.values()):
                return "closure_pending"
        for key in ("binding", "nutrient_binding", "acid_binding", "circulation_binding"):
            binding = t.entry.options.get("control", {}).get(key)
            if not binding:
                continue
            try:
                state = t.hass.states.get(resolve(t.hass, binding))
                if state is None or state.state != "off":
                    return "output_not_off"
            except Exception:
                return "capability_lost"
        p, _ = read(t)
        if self.seen and any(not getattr(c, s) for s in p["required_stages"]):
            return "required_stage_disabled"
        return None

    def observe(self):
        if self.closed:
            return
        self.remember_registry_targets()
        try:
            p, _ = read(self.tank)
        except Exception:
            self.invalidate("policy_disabled")
            return
        current = self.settings()
        if current != self.fingerprint:
            self.fingerprint = current
            self.invalidate("settings_changed")
        c = self.tank.control
        f = c.flow
        rp = f.run_plan
        if rp and f.active and rp["run_id"] != self.seen:
            self.invalidate("new_run")
            self.seen = rp["run_id"]
            self.generation = c.generation
            self.consumed = False
            self.completion = dict(state="running", run_id=self.seen, settled_at=None)
        if self.candidate:
            reason = self.guard() or self.health(p)
            if self.hard is not None and self.clock() >= self.hard:
                reason = "expired"
            if reason:
                self.invalidate(reason)
        if (
            self.completion["state"] == "running"
            and rp
            and rp["run_id"] == self.seen
            and not f.active
        ):
            if f.outcome in ("aborted", "fault"):
                self.completion["state"] = f.outcome
                self.invalidate(f.outcome)
            elif f.outcome == "completed":
                reason = None
                if any(not rp["enabled_stages"][s] for s in p["required_stages"]):
                    reason = "required_stage_disabled"
                elif any(
                    rp["enabled_stages"][s] and r["result"] != "completed"
                    for s, r in f.records.items()
                ):
                    reason = "stage_skipped"
                elif any(f.records[s]["result"] != "completed" for s in p["required_stages"]):
                    reason = "run_incomplete"
                elif not f.times or any(
                    s not in f.times and s != "refill" for s in p["required_stages"]
                ):
                    reason = "no_actual_start"
                elif rp["settings_revision"] != self.tank.entry.options.get(
                    "settings_revision", 0
                ) or rp["flow_plan_revision"] != self.tank.entry.options.get(
                    "flow_plan_revision", 0
                ):
                    reason = "settings_changed"
                closure = self.guard()
                if closure == "closure_pending":
                    return
                reason = reason or closure
                self.completion = dict(
                    state="incomplete" if reason else "completed",
                    run_id=self.seen,
                    settled_at=dt_util.utcnow().isoformat(),
                )
                if reason or self.consumed:
                    self.invalidate(reason or "candidate_consumed")
                else:
                    self.candidate = self.seen
                    self.reset()
                    self.reasons = ["stabilizing"]
        self.schedule()

    def deadline(self):
        deadlines = [v[1] for v in self.samples.values()]
        if self.granted and self.hard is not None:
            deadlines.append(self.hard)
        return min(deadlines) if deadlines else None

    def schedule(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None
        deadline = self.deadline()
        if not self.closed and deadline is not None:
            self.timer = self.tank.hass.loop.call_at(
                max(self.tank.hass.loop.time(), deadline), self.expire
            )

    @callback
    def expire(self):
        self.timer = None
        now = self.clock()
        if (self.hard is not None and now >= self.hard) or any(
            now >= v[1] for v in self.samples.values()
        ):
            reason = "expired" if self.hard is not None and now >= self.hard else "source_stale"
            self.samples = {k: v for k, v in self.samples.items() if now < v[1]}
            self.invalidate(reason)
            self.notify()
        else:
            self.schedule()

    @callback
    def close(self, event=None):
        if self.closed:
            return
        self.closed = True
        self.invalidate("entry_inactive")
        for unsub in self.unsubs:
            unsub()
        self.unsubs.clear()
        self.notify()

    def dto(self):
        t = self.tank
        p, rev = read(t)
        self.observe()
        health = self.health(p)
        if health and (self.count or self.candidate):
            self.invalidate(health)
        registry = er.async_get(t.hass)
        entities = {}
        for key, domain in (("quality_status", "sensor"), ("irrigation_permit", "binary_sensor")):
            identity = registry.async_get_entity_id(domain, DOMAIN, f"{t.entry.entry_id}:{key}")
            row = registry.async_get(identity) if identity else None
            entities[key] = (
                identity
                if row
                and not row.disabled_by
                and row.config_entry_id == t.entry.entry_id
                and t.hass.states.get(identity) is not None
                else None
            )
        state = "qualified" if self.qualified(p) else "stabilizing"
        reasons = [] if state == "qualified" else ["stabilizing"]
        if health:
            state = "out_of_range" if health == "out_of_range" else "invalid"
            reasons = [health]
        if not p["enabled"]:
            state = "disabled"
            reasons = ["policy_disabled"]
        if t.entry.options.get("control_contract_version") != 5:
            state = "unsupported"
            reasons = ["unsupported_control"]
        if state in ("disabled", "unsupported") and self.candidate:
            self.invalidate(reasons[0])
        expiry = self.deadline() if self.granted else None
        expires = (
            (
                self._projection_utc + timedelta(seconds=expiry - self._projection_monotonic)
            ).isoformat()
            if expiry is not None
            else None
        )
        return dict(
            schema_version=1,
            config_entry_id=t.entry.entry_id,
            epoch=self.epoch,
            observation_revision=self.observation_revision,
            policy_revision=rev,
            settings_revision=t.entry.options.get("settings_revision", 0),
            flow_plan_revision=t.entry.options.get("flow_plan_revision", 0),
            policy=p,
            entities=entities,
            quality=dict(
                state=state, stable_count=self.count, stable_since=self.since, reasons=reasons
            ),
            completion=dict(self.completion),
            permit=dict(
                granted=self.granted,
                run_id=self.candidate if self.granted else None,
                expires_at=expires,
                reasons=[] if self.granted else list(self.reasons),
            ),
        )
