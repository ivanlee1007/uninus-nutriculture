"""Private entry-owned notification policy. No control locks or entry options."""

import asyncio
import json
import re
from copy import deepcopy
from pathlib import Path

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN

MAX = 2**53 - 1
EVENTS = (
    "start",
    "stop",
    "completed",
    "incomplete",
    "failed",
    "danger",
    "timeout",
    "stop_unconfirmed",
)
DEFAULT = dict(enabled=False, provider=None, target_binding=None, events=[], cooldown_seconds=300)


def text(value, maximum=128):
    return (
        type(value) is str
        and 1 <= len(value) <= maximum
        and all(
            not (
                ord(c) < 32
                or 127 <= ord(c) <= 159
                or 0xD800 <= ord(c) <= 0xDFFF
                or ord(c)
                in (
                    0x61C,
                    0x200E,
                    0x200F,
                    0x202A,
                    0x202B,
                    0x202C,
                    0x202D,
                    0x202E,
                    0x2066,
                    0x2067,
                    0x2068,
                    0x2069,
                )
            )
            for c in value
        )
    )


def integer(value):
    return type(value) is int and 0 <= value <= MAX


def validate_policy(value, *, stored=False):
    target = "target_binding" if stored else "target_entity_id"
    if type(value) is not dict or set(value) != {
        "enabled",
        "provider",
        target,
        "events",
        "cooldown_seconds",
    }:
        raise ServiceValidationError("invalid_notification_policy")
    if (
        type(value["enabled"]) is not bool
        or value["provider"] not in (None, "persistent_notification", "notify_entity")
        or type(value["events"]) is not list
        or len(value["events"]) > 8
        or any(type(v) is not str or v not in EVENTS for v in value["events"])
        or len(set(value["events"])) != len(value["events"])
        or type(value["cooldown_seconds"]) is not int
        or not 60 <= value["cooldown_seconds"] <= 86400
    ):
        raise ServiceValidationError("invalid_notification_policy")
    if value["enabled"] and (value["provider"] is None or not value["events"]):
        raise ServiceValidationError("invalid_notification_policy")
    binding = value[target]
    if value["provider"] != "notify_entity":
        if binding is not None:
            raise ServiceValidationError("invalid_notification_policy")
    elif stored:
        if (
            type(binding) is not dict
            or set(binding)
            != {"entity_id", "registry_entry_id", "platform", "unique_id", "config_entry_id"}
            or not text(binding["entity_id"], 255)
            or re.fullmatch(r"notify\.[a-z0-9_]+", binding["entity_id"]) is None
            or not text(binding["registry_entry_id"])
            or not text(binding["platform"])
            or not text(binding["unique_id"], 512)
            or binding["config_entry_id"] is not None
            and not text(binding["config_entry_id"])
        ):
            raise ServiceValidationError("invalid_notification_policy")
    elif not text(binding, 255) or re.fullmatch(r"notify\.[a-z0-9_]+", binding) is None:
        raise ServiceValidationError("invalid_provider")
    return deepcopy(value)


class Notifications:
    def __init__(self, tank):
        self.tank = tank
        self.epoch = tank.results.epoch
        self.lock = asyncio.Lock()
        self.closed = False
        self.indeterminate = False
        self.revision = 0
        self.policy = deepcopy(DEFAULT)
        self.catalog = []
        self.deliveries = []
        self.io = set()
        from .notification_dispatch import Dispatcher

        self.dispatcher = Dispatcher(self)
        self.store = Store(
            tank.hass,
            1,
            DOMAIN + ".notification_v1." + tank.entry.entry_id,
            private=True,
            atomic_writes=True,
        )
        self.unsub = tank.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.close)
        self.catalog_unsubs = [
            tank.hass.bus.async_listen(EVENT_STATE_CHANGED, self.changed),
            tank.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self.changed),
        ]
        tank.entry.async_on_unload(self.close)

    def live(self):
        entry = self.tank.entry
        return (
            not self.closed
            and self.tank.active
            and entry.runtime_data is self.tank
            and not entry.disabled_by
            and self.tank.hass.config_entries.async_get_entry(entry.entry_id) is entry
            and self.tank.hass.state
            not in (CoreState.stopping, CoreState.final_write, CoreState.stopped)
        )

    @callback
    def close(self, event=None):
        if self.closed:
            return
        self.closed = True
        self.dispatcher.close()
        self.unsub()
        for unsub in self.catalog_unsubs:
            unsub()
        self.catalog_unsubs.clear()

    @callback
    def changed(self, event):
        if not self.closed and (
            event.data.get("entity_id", "").startswith("notify.")
            or event.event_type == er.EVENT_ENTITY_REGISTRY_UPDATED
        ):
            self.refresh_catalog()

    def refresh_catalog(self):
        from .notification_provider import catalog, resolve

        self.catalog = catalog(self.tank.hass, self.policy["target_binding"])
        self.provider_available = self.policy["provider"] == "persistent_notification"
        if self.policy["provider"] == "notify_entity":
            try:
                resolve(self.tank.hass, self.policy["target_binding"])
                self.provider_available = True
            except ServiceValidationError:
                self.provider_available = False

    def dto(self):
        availability = (
            "indeterminate"
            if self.indeterminate
            else "disabled"
            if not self.policy["enabled"]
            else "available"
            if getattr(self, "provider_available", False)
            else "unavailable"
        )
        return deepcopy(
            dict(
                schema_version=1,
                config_entry_id=self.tank.entry.entry_id,
                epoch=self.epoch,
                revision=self.revision,
                policy=self.policy,
                availability=availability,
                error="indeterminate"
                if self.indeterminate
                else "provider_unavailable"
                if availability == "unavailable"
                else None,
                catalog=self.catalog,
                deliveries=self.deliveries,
            )
        )

    def physical(self):
        """Read the independent disk envelope, never the native Store cache."""
        try:
            with Path(self.store.path).open("rb") as stream:
                raw = stream.read(65537)
        except FileNotFoundError:
            return None
        if len(raw) > 65536:
            raise ValueError("storage_failed")

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("storage_failed")
                result[key] = value
            return result

        def constant(value):
            raise ValueError("storage_failed")

        envelope = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
        if (
            type(envelope) is not dict
            or set(envelope) != {"version", "minor_version", "key", "data"}
            or type(envelope["version"]) is not int
            or envelope["version"] != 1
            or type(envelope["minor_version"]) is not int
            or envelope["minor_version"] != 1
            or envelope["key"] != self.store.key
        ):
            raise ValueError("storage_failed")
        doc = envelope["data"]
        if (
            type(doc) is not dict
            or set(doc) != {"schema_version", "config_entry_id", "revision", "policy"}
            or type(doc["schema_version"]) is not int
            or doc["schema_version"] != 1
            or type(doc["config_entry_id"]) is not str
            or doc["config_entry_id"] != self.tank.entry.entry_id
            or not integer(doc["revision"])
        ):
            raise ValueError("storage_failed")
        validate_policy(doc["policy"], stored=True)
        return doc

    async def _persistence_wait(self, task):
        cancelled = False
        while not task.done():
            try:
                await asyncio.wait((task,))
            except asyncio.CancelledError:
                cancelled = True
                self.indeterminate = True
        if cancelled:
            if not task.cancelled():
                task.exception()
            raise asyncio.CancelledError()
        return task.result()

    async def _persistence_job(self, coroutine):
        # Register before the first executor: Core otherwise cancels its Future
        # as background work even though the physical thread is still running.
        try:
            child = self.tank.hass.async_create_task(coroutine, eager_start=False)
        except BaseException:
            coroutine.close()
            raise
        return await self._persistence_wait(child)

    async def owned(self, coroutine):
        job = self._persistence_job(coroutine)
        try:
            task = self.tank.hass.async_create_task(job, eager_start=False)
        except BaseException:
            job.close()
            coroutine.close()
            raise
        self.io.add(task)
        try:
            return await self._persistence_wait(task)
        finally:
            self.io.discard(task)

    async def drain(self):
        cancelled = False
        while self.io:
            for task in tuple(self.io):
                try:
                    await self._persistence_wait(task)
                except asyncio.CancelledError:
                    cancelled = cancelled or bool(asyncio.current_task().cancelling())
                except Exception:
                    pass
                finally:
                    if task.done():
                        self.io.discard(task)
        if cancelled:
            raise asyncio.CancelledError()

    async def setup(self):
        try:
            await self.load()
        except Exception:
            self.indeterminate = True
        self.refresh_catalog()

    async def _persistence_fence(self, fence):
        if fence is not None:
            await fence()
        if not self.live():
            raise ServiceValidationError("entry_not_loaded")

    async def load(self, fence=None):
        try:
            await self._persistence_fence(fence)
            before = await self.owned(self._persistence_read())
            await self._persistence_fence(fence)
            fresh = Store(self.tank.hass, 1, self.store.key, private=True, atomic_writes=True)
            loaded = await self.owned(fresh.async_load())
            await self._persistence_fence(fence)
            after = await self.owned(self._persistence_read())
            await self._persistence_fence(fence)
            if before != after or loaded != after:
                raise ValueError("storage_failed")
            if after is None:
                if self.revision or self.indeterminate:
                    raise ValueError("storage_failed")
                return
            if after["revision"] < self.revision:
                raise ValueError("storage_failed")
            self.policy = deepcopy(after["policy"])
            self.revision = after["revision"]
            self.indeterminate = False
        except BaseException:
            self.indeterminate = True
            raise

    async def _persistence_read(self):
        return await self.tank.hass.async_add_executor_job(self.physical)

    async def _persistence_native_save(self, candidate, fence):
        store = self.store
        lock = getattr(store, "_uninus_notification_write_lock", None)
        if lock is None:
            lock = store._uninus_notification_write_lock = asyncio.Lock()
        async with lock:
            await self._persistence_fence(fence)
            native = store._async_write_data
            had_override = "_async_write_data" in store.__dict__
            completed = False

            async def observe(data):
                nonlocal completed
                await native(data)
                if data.get("key") == store.key and data.get("data") is candidate:
                    completed = True

            store._async_write_data = observe
            try:
                # Native serialization/writer/error logging remain unchanged.
                await store.async_save(candidate)
                if not completed:
                    raise ServiceValidationError("storage_failed")
            finally:
                if had_override:
                    store._async_write_data = native
                else:
                    del store._async_write_data

    async def save(self, policy, fence):
        candidate = dict(
            schema_version=1,
            config_entry_id=self.tank.entry.entry_id,
            revision=self.revision + 1,
            policy=validate_policy(policy, stored=True),
        )
        await fence()
        try:
            await self.owned(self._persistence_native_save(candidate, fence))
            await fence()
            actual = await self.owned(self._persistence_read())
            await fence()
            if actual != candidate:
                raise ValueError("storage_failed")
        except BaseException:
            self.indeterminate = True
            raise
        self.revision = candidate["revision"]
        self.policy = deepcopy(candidate["policy"])

    async def reconcile(self, fence):
        await self.drain()
        await self._persistence_fence(fence)
        await self.load(fence)

    def enqueue(self, event):
        self.dispatcher.enqueue(event)
