"""Notification-only native Options. Never create_entry with control options."""

import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import selector

from .notification_api import execute
from .notifications import EVENTS
from .options_auth import human_options, options_context


class NotificationOptions:
    @human_options
    async def async_step_notifications(self, user_input=None):
        def retire(reason):
            self._notification_dto = None
            self._notification_fields = set()
            self._notification_owner = None
            self._notification_retired = reason
            return self.async_abort(reason=reason)

        if getattr(self, "_notification_retired", None):
            return retire(self._notification_retired)
        if user_input is not None and user_input.get("action") == "cancel":
            return retire("notification_cancelled")
        errors = {}
        ctx = options_context(self)
        base = {"config_entry_id": self.config_entry.entry_id}
        if not hasattr(self, "_notification_owner"):
            self._notification_owner = getattr(self.config_entry, "runtime_data", None)

        async def current():
            fresh = await execute(self.hass, ctx, "get", base)
            if self.config_entry.runtime_data is not self._notification_owner:
                raise ServiceValidationError("entry_not_loaded")
            cached = getattr(self, "_notification_dto", None)
            if cached is not None and fresh["epoch"] != cached["epoch"]:
                raise ServiceValidationError("notification_conflict")
            return fresh

        try:
            fresh = await current()
            if not hasattr(self, "_notification_dto"):
                self._notification_dto = fresh
            dto = self._notification_dto
            if user_input is not None:
                action = user_input["action"]
                if action == "reconcile":
                    self._notification_dto = await execute(
                        self.hass, ctx, "reconcile", {**base, "expected_epoch": dto["epoch"]}
                    )
                elif (
                    action == "save"
                    and user_input["provider"] == "notify_entity"
                    and not user_input.get("target_entity_id")
                    and "target_entity_id" not in getattr(self, "_notification_fields", set())
                ):
                    # Provider change reveals its target picker, without a mutation attempt.
                    pass
                elif action == "save":
                    cooldown = user_input["cooldown_seconds"]
                    if type(cooldown) is float and cooldown.is_integer():
                        cooldown = int(cooldown)
                    provider = user_input["provider"]
                    p = dict(
                        enabled=user_input["enabled"],
                        provider=None if provider == "none" else provider,
                        target_entity_id=user_input.get("target_entity_id")
                        if provider == "notify_entity"
                        else None,
                        events=user_input["events"],
                        cooldown_seconds=cooldown,
                    )
                    await execute(
                        self.hass,
                        ctx,
                        "save",
                        {
                            **base,
                            "expected_epoch": dto["epoch"],
                            "expected_revision": dto["revision"],
                            "policy": p,
                        },
                    )
                    return self.async_abort(reason="notification_saved")
        except (ServiceValidationError, Unauthorized) as err:
            allowed = {
                "entry_not_loaded",
                "settings_schema_mismatch",
                "invalid_notification_policy",
                "invalid_provider",
                "notification_conflict",
                "notification_not_found",
                "storage_failed",
                "indeterminate",
            }
            code = "unauthorized" if isinstance(err, Unauthorized) else str(err)
            errors["base"] = (
                code if code in allowed or code == "unauthorized" else "invalid_notification_policy"
            )
        # Fresh authority is not a fresh CAS baseline: never rebase a stale Save.
        try:
            await current()
        except (ServiceValidationError, Unauthorized) as err:
            return retire("unauthorized" if isinstance(err, Unauthorized) else str(err))
        if errors.get("base") in ("unauthorized", "entry_not_loaded"):
            return retire(errors["base"])
        dto = getattr(self, "_notification_dto", None)
        if dto is None:
            return retire(errors.get("base", "entry_not_loaded"))
        policy = dto["policy"]
        values = {**policy, "provider": policy["provider"] or "none", **(user_input or {})}
        fields = {
            vol.Required("enabled", default=values["enabled"]): selector.BooleanSelector(),
            vol.Required("provider", default=values["provider"]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["none", "persistent_notification", "notify_entity"]
                )
            ),
            vol.Required("events", default=values["events"]): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(EVENTS), multiple=True)
            ),
            vol.Required(
                "cooldown_seconds", default=values["cooldown_seconds"]
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=60, max=86400, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required("action", default="save"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=["save", "cancel", "reconcile"])
            ),
        }
        # Initial provider selector includes target; PN selected hides it on reopen.
        if values["provider"] in ("none", "notify_entity"):
            binding = policy["target_binding"]
            fields[
                vol.Optional(
                    "target_entity_id",
                    description={"suggested_value": binding["entity_id"] if binding else None},
                )
            ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="notify"))
        self._notification_fields = {str(k) for k in fields}
        return self.async_show_form(
            step_id="notifications", data_schema=vol.Schema(fields), errors=errors
        )
