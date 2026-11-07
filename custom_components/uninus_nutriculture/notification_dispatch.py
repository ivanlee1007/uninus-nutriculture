"""Bounded notification handoff, independent of every actuator owner/lock."""

import asyncio
import hashlib
from collections import deque
from copy import deepcopy

from homeassistant.components import persistent_notification
from homeassistant.util import dt as dt_util

KINDS = {
    "accepted": "start",
    "stopped": "stop",
    "completed": "completed",
    "incomplete": "incomplete",
    "failed": "failed",
    "stop_unconfirmed": "stop_unconfirmed",
    "ph_low": "danger",
    "ec_high": "danger",
    "ph_high": "danger",
}
TIMEOUTS = {"flow_timeout", "ec_timeout", "ph_timeout", "refill_timeout", "sample_timeout"}
MESSAGES = {
    "accepted": "流程已受理（不代表已完成）。",
    "running": "流程執行中。",
    "stopping": "流程停止中。",
    "completed": "流程已閉合完成；品質與灌溉許可請另查。",
    "stopped": "流程已停止並確認關閉。",
    "incomplete": "流程已閉合，但未完整完成。",
    "failed": "流程已閉合，結果失敗。",
    "stop_unconfirmed": "停止尚未確認，請檢查設備。",
    "ph_low": "pH 低於危險下限。",
    "ec_high": "EC 高於危險上限。",
    "ph_high": "pH 高值告警。",
}
CRITICAL = {"completed", "stopped", "incomplete", "failed", "stop_unconfirmed"}


class Dispatcher:
    def __init__(self, notifications):
        self.n = notifications
        self.hass = notifications.tank.hass
        self.slots = self.hass.data.setdefault("uninus_nutriculture_notification_slots", set())
        self.entry_slots = self.hass.data.setdefault(
            "uninus_nutriculture_notification_entry_slots", {}
        )
        self.entry_id = notifications.tank.entry.entry_id
        self.queue = deque()
        self.dedupe = deque(maxlen=64)
        self.cooldowns = {}
        self.episodes = deque(maxlen=64)
        self.alarms = {}
        self.faults = {}
        self.worker = None
        self.native = None
        self.clock = self.hass.loop.time

    def valid(self, event, policy, revision):
        n = self.n
        return (
            n.live()
            and not n.indeterminate
            and n.policy["enabled"]
            and n.epoch == event["epoch"]
            and n.revision == revision
            and n.policy == policy
            and event["config_entry_id"] == n.tank.entry.entry_id
        )

    def record(self, event, status, code=None):
        n = self.n
        if not n.live():
            return
        row = next((r for r in n.deliveries if r["event_id"] == event["event_id"]), None)
        if row is None:
            row = dict(
                event_id=event["event_id"],
                kind=event["kind"],
                status=status,
                code=code,
                acknowledged=False,
                updated_at=dt_util.utcnow().isoformat(),
            )
            n.deliveries.append(row)
            n.deliveries[:] = n.deliveries[-32:]
        else:
            row.update(status=status, code=code, updated_at=dt_util.utcnow().isoformat())

    def enqueue(self, event):
        n = self.n
        p = n.policy
        if (
            not n.live()
            or n.indeterminate
            or not p["enabled"]
            or event["epoch"] != n.epoch
            or event["config_entry_id"] != n.tank.entry.entry_id
            or event["event_id"] in self.dedupe
        ):
            return
        self.dedupe.append(event["event_id"])
        kind = event["kind"]
        category = (
            "timeout" if kind == "stopping" and event["reason"] in TIMEOUTS else KINDS.get(kind)
        )
        episodes = self.correlate(event)
        if category not in p["events"]:
            return
        now = self.clock()
        cooldown_key = kind
        if now < self.cooldowns.get(cooldown_key, float("-inf")):
            self.record(event, "suppressed", "cooldown")
            return
        if len(self.queue) >= 16:
            victim = (
                next((j for j in self.queue if j[0]["kind"] not in CRITICAL), None)
                if kind in CRITICAL
                else None
            )
            if victim is None:
                self.record(event, "suppressed", "queue_full")
                return
            self.queue.remove(victim)
            self.record(victim[0], "suppressed", "queue_full")
        self.cooldowns[cooldown_key] = now + p["cooldown_seconds"]
        self.queue.append((deepcopy(event), now, deepcopy(p), n.revision, episodes))
        self.record(event, "queued")
        if self.worker is None or self.worker.done():
            self.worker = self.hass.async_create_background_task(
                self.run(), "notification queue", eager_start=False
            )

    def correlate(self, event):
        """Capture the observed fault occurrence, not the lifetime of a run."""
        kind, why, run = event["kind"], event["reason"], event["run"]
        keys = []
        if KINDS.get(kind) == "danger":
            self.alarms[kind] = event["event_id"]
            keys.append((kind, event["event_id"]))
            if run and (run["run_id"], kind) in self.faults:
                if self.faults[(run["run_id"], kind)] is None:
                    self.faults[(run["run_id"], kind)] = keys[-1]
        if run:
            ident = run["run_id"]
            if why in TIMEOUTS:
                keys.append((ident, why))
            if kind in ("stop_unconfirmed", "failed"):
                keys.append((ident, "stop_unconfirmed"))
            if kind in ("stopping", "failed"):
                alarm = {"ph_danger": "ph_low", "ec_danger": "ec_high"}.get(why, why)
                state = self.n.tank.results.alarms.get(alarm)
                active = state[1] if isinstance(state, tuple) else state
                key = (alarm, self.alarms[alarm]) if active and alarm in self.alarms else None
                if kind == "stopping" and KINDS.get(alarm) == "danger":
                    # Bind the cause at fault onset, before OFF can outlive recovery.
                    self.faults[(ident, alarm)] = key
                    if len(self.faults) > 64:
                        self.faults.pop(next(iter(self.faults)))
                if kind == "failed":
                    key = self.faults.get((ident, alarm), key)
                    if key is not None:
                        keys.append(key)
        return tuple(keys)

    async def handoff(self, event, policy, revision):
        # Keep cancellation attached to an owned child until actual provider/executor settles.
        async def invoke():
            if not self.valid(event, policy, revision):
                return
            title = "UNiNUS 流程通知"
            message = MESSAGES[event["kind"]]
            if policy["provider"] == "persistent_notification":
                opaque = hashlib.sha256(
                    (event["config_entry_id"] + event["event_id"]).encode()
                ).hexdigest()[:32]
                persistent_notification.async_create(self.hass, message, title, "uninus_" + opaque)
            else:
                from .notification_provider import send

                await send(
                    self.hass,
                    policy["target_binding"],
                    message,
                    title,
                    lambda: self.valid(event, policy, revision),
                )

        child = self.hass.async_create_task(
            invoke(), "typed notification handoff", eager_start=False
        )
        cancelled = False
        while not child.done():
            try:
                await asyncio.shield(child)
            except asyncio.CancelledError:
                cancelled = True
        result = child.result()
        if cancelled:
            raise asyncio.CancelledError
        return result

    async def run(self):
        try:
            while self.queue and self.n.live():
                event, queued, policy, revision, episodes = self.queue[0]
                if not self.valid(event, policy, revision):
                    self.queue.popleft()
                    self.record(event, "cancelled", "revoked")
                    continue
                # Merge only a successful handoff under this exact policy fence.
                # Queued, evicted, expired, revoked or failed attempts are not notices.
                if any(
                    key in episodes and old_policy == policy and old_revision == revision
                    for key, old_policy, old_revision in self.episodes
                ):
                    self.queue.popleft()
                    # There is no second delivery to ACK; keep the first notice.
                    self.n.deliveries[:] = [
                        row for row in self.n.deliveries if row["event_id"] != event["event_id"]
                    ]
                    continue
                if self.clock() - queued >= 60:
                    self.queue.popleft()
                    self.record(event, "suppressed", "expired")
                    continue
                # Stable entry ownership outlives a retired runtime, just like global slots.
                if self.entry_id in self.entry_slots or len(self.slots) >= 2:
                    await asyncio.sleep(0.05)
                    continue
                self.queue.popleft()
                task = self.hass.async_create_background_task(
                    self.handoff(event, policy, revision),
                    "native notification slot",
                    eager_start=False,
                )
                self.native = task
                self.slots.add(task)
                self.entry_slots[self.entry_id] = task

                def settled(t):
                    self.slots.discard(t)
                    if self.entry_slots.get(self.entry_id) is t:
                        del self.entry_slots[self.entry_id]
                    if not t.cancelled():
                        t.exception()

                task.add_done_callback(settled)
                done, _ = await asyncio.wait({task}, timeout=5)
                if not self.valid(event, policy, revision):
                    if not task.done():
                        task.cancel()
                        while not task.done() and self.n.live():
                            await asyncio.sleep(0.05)
                    continue
                if not done:
                    self.record(event, "timed_out", "provider_timeout")
                    task.cancel()
                    # Slot remains quarantined until provider actually settles.
                    while not task.done() and self.n.live():
                        await asyncio.sleep(0.05)
                elif task.cancelled():
                    self.record(event, "cancelled", "cancelled")
                elif task.exception() is not None:
                    from homeassistant.exceptions import ServiceValidationError

                    error = task.exception()
                    code = (
                        "provider_unavailable"
                        if isinstance(error, ServiceValidationError)
                        and str(error) == "provider_unavailable"
                        else "provider_failed"
                    )
                    self.record(event, "failed", code)
                else:
                    self.record(event, "handoff_returned")
                    for key in episodes:
                        self.episodes.append((key, policy, revision))
        except asyncio.CancelledError:
            if self.native is not None and not self.native.done():
                self.native.cancel()
            raise

    def close(self):
        self.queue.clear()
        if self.worker is not None and not self.worker.done():
            self.worker.cancel()
