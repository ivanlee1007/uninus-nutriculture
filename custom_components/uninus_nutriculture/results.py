"""Ephemeral result observation. Never dispatch, refresh control or confer permit."""

from copy import deepcopy
from uuid import uuid4

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED
from homeassistant.core import Context, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .control_settings import STAGES, resolve

PHASES = frozenset(
    (
        "confirming_off",
        "mixing",
        "pulsing",
        "refilling",
        "stabilizing",
        "starting",
        "starting_circulation",
        "stopping",
        "waiting_condition",
        "waiting_delay",
        "waiting_resource",
        "waiting_sample",
    )
)
RESULTS = frozenset(
    ("completed", "aborted", "fault", "skipped_disabled", "skipped_weekday", "blocked_dependency")
)
REASONS = frozenset(
    (
        "circulation_lost",
        "condition_not_met",
        "delay_pending",
        "dependency_not_started",
        "dose_budget_exhausted",
        "ec_danger",
        "ec_high",
        "ec_timeout",
        "emergency_stop",
        "entry_inactive",
        "flow_timeout",
        "level_unsafe",
        "no_actual_start",
        "none",
        "operation_failed",
        "output_already_owned",
        "output_identity_invalid",
        "output_not_off",
        "output_unbound",
        "output_unexpected",
        "ph_danger",
        "ph_high",
        "ph_low",
        "ph_timeout",
        "refill_timeout",
        "resource_chemical",
        "restart_output_not_off",
        "revoked",
        "sample_invalid",
        "sample_timeout",
        "source_invalid",
        "stage_skipped",
        "start_cancelled",
        "start_unconfirmed",
        "stop_unconfirmed",
        "weekday",
    )
)
MAX = 2**53 - 1


def reason(value):
    return value if value in REASONS else "operation_failed"


def pending(task):
    return task is not None and not task.done()


class ResultCoordinator:
    def __init__(self, tank):
        self.tank = tank
        self.epoch = uuid4().hex
        self.sequence = 0
        self.seen = None
        self.bindings = []
        self.run = None
        self.closed = False
        self.timer = None
        self.alarms = {}
        self.cache = dict(
            schema_version=1,
            config_entry_id=tank.entry.entry_id,
            epoch=self.epoch,
            observation_revision=0,
            support="supported"
            if tank.entry.options.get("control_contract_version") == 5
            else "unsupported",
            current_run=None,
            last_result=None,
            latest_event=None,
        )
        self.unsubs = [
            tank.hass.bus.async_listen(EVENT_STATE_CHANGED, self.changed),
            tank.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self.changed),
            tank.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.close),
        ]
        tank.entry.async_on_unload(self.close)

    def dto(self):
        return deepcopy(self.cache)

    @callback
    def close(self, event=None):
        self.closed = True
        if self.timer:
            self.timer.cancel()
            self.timer = None
        for unsub in self.unsubs:
            unsub()
        self.unsubs.clear()

    @callback
    def changed(self, event):
        if not self.closed:
            self.observe()
            self.notify()

    def notify(self):
        # Observation must not repaint Number/output state or any control projection.
        identity = f"{self.tank.entry.entry_id}:result_status"
        for listener in tuple(self.tank.listeners):
            owner = getattr(listener, "__self__", None)
            if getattr(owner, "unique_id", None) == identity:
                listener()

    def remember(self):
        c = self.tank.control
        values = [
            self.tank.entry.options.get("control", {}).get(k)
            for k in ("binding", "nutrient_binding", "acid_binding", "circulation_binding")
        ]
        for s in STAGES:
            owner = c.flow.stage(s)
            values.extend(getattr(owner, "bindings", {}).values())
            values.append(getattr(owner, "binding", None))
        for value in values:
            if value and value not in self.bindings:
                self.bindings.append(deepcopy(value))

    def closure(self):
        c = self.tank.control
        f = c.flow
        if (
            f.active
            or f.stopping
            or c.running
            or c.leases
            or c.late_on
            or any(pending(t) for t in (c.on_task, c.off_task))
        ):
            return False
        for s in STAGES:
            owner = f.stage(s)
            if (
                owner.owns_io
                or getattr(owner, "cleanup_lock", None)
                and owner.cleanup_lock.locked()
                or any(pending(t) for t in owner.operations.values())
            ):
                return False
            if pending(getattr(owner, "task", None)) or pending(
                getattr(owner, "cleanup_task", None)
            ):
                return False
        for binding in self.bindings:
            try:
                state = self.tank.hass.states.get(resolve(self.tank.hass, binding))
            except Exception:
                return False
            if state is None or state.state != "off":
                return False
        return True

    def rotate_epoch(self):
        self.epoch = uuid4().hex
        self.sequence = 0
        self.cache.update(epoch=self.epoch, observation_revision=0, latest_event=None)
        for row in (self.run, self.cache["current_run"], self.cache["last_result"]):
            if row is not None:
                row["epoch"] = self.epoch
        n = getattr(self.tank, "notifications", None)
        if n is not None:
            n.epoch = self.epoch
            n.deliveries.clear()
            n.dispatcher.queue.clear()
            n.dispatcher.dedupe.clear()
            # Preserve cooldown/episode state: epoch rotation must not replay alarms.

    def advance(self):
        if self.cache["observation_revision"] >= MAX:
            self.rotate_epoch()
        self.cache["observation_revision"] += 1

    def event(self, kind, why, run, now):
        if self.sequence >= MAX:
            self.rotate_epoch()
            self.advance()
        if run is not None:
            run = deepcopy(run)
            run["epoch"] = self.epoch
        self.sequence += 1
        event = dict(
            schema_version=1,
            config_entry_id=self.tank.entry.entry_id,
            epoch=self.epoch,
            observation_revision=self.cache["observation_revision"],
            sequence=self.sequence,
            event_id=f"{self.epoch}:{self.sequence}",
            kind=kind,
            reason=why,
            occurred_at=now,
            run=deepcopy(run),
        )
        self.cache["latest_event"] = deepcopy(event)
        self.tank.hass.bus.async_fire(DOMAIN + "_result_v1", deepcopy(event), context=Context())
        notifications = getattr(self.tank, "notifications", None)
        if notifications is not None:
            notifications.enqueue(event)

    def observe(self):
        if self.closed:
            return
        supported = self.tank.entry.options.get("control_contract_version") == 5
        if not supported:
            return
        if self.cache["support"] != "supported":
            self.cache["support"] = "supported"
            self.advance()
        c = self.tank.control
        f = c.flow
        plan = f.run_plan
        now = None
        if plan and f.active and plan["run_id"] != self.seen:
            self.seen = plan["run_id"]
            self.bindings = []
            self.remember()
            now = dt_util.utcnow().isoformat()
            self.run = dict(
                run_id=self.seen,
                epoch=self.epoch,
                settings_revision=plan["settings_revision"],
                flow_plan_revision=plan["flow_plan_revision"],
                state="accepted",
                closure="pending",
                reason="none",
                accepted_at=now,
                started_at=None,
                finished_at=None,
                transition_at=now,
                stages=deepcopy(f.records),
            )
            self.cache["current_run"] = deepcopy(self.run)
            self.advance()
            self.event("accepted", "none", self.run, now)
        if self.run is not None:
            self.remember()
            updated = deepcopy(self.run)
            for s, record in f.records.items():
                row = {
                    k: deepcopy(record[k])
                    for k in ("phase", "result", "started_at", "settled_at", "waiting_reason")
                }
                if row["phase"] is not None and row["phase"] not in PHASES:
                    row["phase"] = "stopping"
                    row["waiting_reason"] = "operation_failed"
                if row["result"] is not None and row["result"] not in RESULTS:
                    row["result"] = "fault"
                if row["waiting_reason"] is not None:
                    row["waiting_reason"] = reason(row["waiting_reason"])
                updated["stages"][s] = row
            starts = [r["started_at"] for r in updated["stages"].values() if r["started_at"]]
            updated["started_at"] = min(starts) if starts else None
            fault = c.fault or (
                "operation_failed"
                if any(r["result"] == "fault" for r in updated["stages"].values())
                else None
            )
            stopping = bool(
                fault or f.stopping or f.outcome == "aborted" or f.generation != c.generation
            )
            if stopping:
                updated.update(state="stopping", reason=reason(fault or "revoked"))
            elif updated["started_at"]:
                updated["state"] = "running"
            done = self.closure()
            if not f.active and not done:
                updated.update(state="stopping", closure="unconfirmed", reason="stop_unconfirmed")
            if done:
                state = (
                    "failed"
                    if fault or self.run["closure"] == "unconfirmed"
                    else "stopped"
                    if stopping
                    else "completed"
                    if f.outcome == "completed"
                    and any(plan["enabled_stages"].values())
                    and all(
                        not plan["enabled_stages"][s]
                        or updated["stages"][s]["result"] == "completed"
                        for s in STAGES
                    )
                    else "incomplete"
                )
                updated.update(state=state, closure="confirmed")
            if updated != self.run:
                now = now or dt_util.utcnow().isoformat()
                old = self.run
                lifecycle = old["state"] != updated["state"] or old["closure"] != updated["closure"]
                if lifecycle:
                    updated["transition_at"] = now
                if done:
                    updated["finished_at"] = now
                    self.cache["current_run"] = None
                    self.cache["last_result"] = deepcopy(updated)
                else:
                    self.cache["current_run"] = deepcopy(updated)
                # Publish the authoritative local row before advance can rotate it.
                # Otherwise the stale pre-rotation copy overwrites the new epoch.
                self.run = updated
                self.advance()
                if lifecycle:
                    kind = (
                        "stop_unconfirmed"
                        if updated["closure"] == "unconfirmed"
                        else updated["state"]
                    )
                    self.event(kind, updated["reason"], updated, now)
                if done:
                    self.run = None
            if self.run is not None and self.timer is None:
                self.timer = self.tank.hass.loop.call_later(1, self.tick)
        self.danger()

    @callback
    def tick(self):
        self.timer = None
        if not self.closed:
            self.observe()
            self.notify()

    def danger(self):
        # Same finite/unit/freshness predicate as control. Read-only, never a fault setter.
        from .flow_settings import source

        safety = self.tank.entry.options.get("safety_parameters", {})
        candidates = {
            "ph_low": (source(self.tank, "ph"), safety.get("ph_danger_low", 3.8), -1),
            "ec_high": (source(self.tank, "ec"), safety.get("ec_danger_high", 1.3), 1),
        }
        for kind, (value, threshold, direction) in candidates.items():
            active = value is not None and direction * value > direction * threshold
            previous = self.alarms.get(kind)
            self.alarms[kind] = (threshold, active)
            if active and previous != (threshold, True):
                self.advance()
                self.event(kind, kind, self.run, dt_util.utcnow().isoformat())
        active = bool(self.tank.control.ph_high_alarm_active)
        previous = self.alarms.get("ph_high", False)
        self.alarms["ph_high"] = active
        if active and not previous:
            self.advance()
            self.event("ph_high", "ph_high", self.run, dt_util.utcnow().isoformat())
