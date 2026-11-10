"""Native selectors for every quality field; never a JSON text editor."""

import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import selector

from .options_auth import human_options, options_context
from .quality_services import execute


class QualityOptions:
    @human_options
    async def async_step_quality(self, user_input=None):
        errors = {}
        try:
            if not hasattr(self, "_quality_dto"):
                self._quality_dto = await execute(
                    self.hass,
                    options_context(self),
                    "get_quality_v1",
                    {"config_entry_id": self.config_entry.entry_id},
                )
            if user_input is not None:
                if user_input["action"] == "cancel":
                    return self.async_abort(reason="quality_cancelled")
                p = {
                    k: user_input[k]
                    for k in (
                        "enabled",
                        "stable_samples",
                        "stable_interval_seconds",
                        "stable_duration_seconds",
                        "permit_ttl_seconds",
                        "required_stages",
                    )
                }
                for k in (
                    "stable_samples",
                    "stable_interval_seconds",
                    "stable_duration_seconds",
                    "permit_ttl_seconds",
                ):
                    if type(p[k]) is float and p[k].is_integer():
                        p[k] = int(p[k])
                p["sources"] = {
                    k: dict(
                        mode=user_input[k + "_mode"],
                        attribute=(user_input.get(k + "_attribute") or None),
                        report_contract_confirmed=user_input[k + "_report_contract_confirmed"],
                    )
                    for k in ("ph", "ec", "level")
                }
                d = self._quality_dto
                await execute(
                    self.hass,
                    options_context(self),
                    "save_quality_policy_v1",
                    dict(
                        config_entry_id=self.config_entry.entry_id,
                        expected_policy_revision=d["policy_revision"],
                        expected_settings_revision=d["settings_revision"],
                        expected_flow_plan_revision=d["flow_plan_revision"],
                        policy=p,
                    ),
                )
                return self.async_abort(reason="quality_saved")
        except (ServiceValidationError, Unauthorized) as err:
            code = "unauthorized" if isinstance(err, Unauthorized) else str(err)
            errors["base"] = (
                code
                if code
                in {
                    "unauthorized",
                    "entry_not_loaded",
                    "settings_schema_mismatch",
                    "quality_conflict",
                    "invalid_quality_policy",
                }
                else "invalid_quality_policy"
            )
        p = getattr(self, "_quality_dto", {}).get("policy")
        if p is None:
            return self.async_abort(reason=errors.get("base", "entry_not_loaded"))
        values = {k: v for k, v in p.items() if k != "sources"}
        for k, r in p["sources"].items():
            values.update(
                {
                    k + "_mode": r["mode"],
                    k + "_attribute": r["attribute"] or "",
                    k + "_report_contract_confirmed": r["report_contract_confirmed"],
                }
            )
        values.update(user_input or {})
        fields = {vol.Required("enabled", default=values["enabled"]): selector.BooleanSelector()}
        for k in (
            "stable_samples",
            "stable_interval_seconds",
            "stable_duration_seconds",
            "permit_ttl_seconds",
        ):
            fields[vol.Required(k, default=values[k])] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=100 if k == "stable_samples" else 86400,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="samples" if k == "stable_samples" else "s",
                )
            )
        fields[vol.Required("required_stages", default=values["required_stages"])] = (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["refill", "nutrient", "acid", "mix"], multiple=True
                )
            )
        )
        for k in ("ph", "ec", "level"):
            fields[vol.Required(k + "_mode", default=values[k + "_mode"])] = (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["reported", "sequence", "timestamp"])
                )
            )
            fields[vol.Optional(k + "_attribute", default=values[k + "_attribute"])] = (
                selector.TextSelector()
            )
            fields[
                vol.Required(
                    k + "_report_contract_confirmed",
                    default=values[k + "_report_contract_confirmed"],
                )
            ] = selector.BooleanSelector()
        fields[vol.Required("action", default="save")] = selector.SelectSelector(
            selector.SelectSelectorConfig(options=["save", "cancel"])
        )
        return self.async_show_form(
            step_id="quality", data_schema=vol.Schema(fields), errors=errors
        )
