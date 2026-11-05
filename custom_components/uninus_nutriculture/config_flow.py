"""Native config and source-binding options flows."""

import math

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import Context, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector

from .const import DOMAIN, SOURCE_KEYS
from .control_settings import DAYS, STAGES, resolve, settings_candidate
from .recipe_options import RecipeOptions


class DosingSelector(selector.NumberSelector):
    """Do not let native float coercion turn a Boolean into a dose limit."""

    def __call__(self, value):
        if isinstance(value, bool):
            raise vol.Invalid("invalid_dosing_parameter")
        result = super().__call__(value)
        if not math.isfinite(result):
            raise vol.Invalid("invalid_dosing_parameter")
        return result


class FeedbackSelector(selector.NumberSelector):
    """Keep native selector rendering while rejecting unsafe coercions."""

    def __call__(self, value):
        if isinstance(value, bool):
            raise vol.Invalid("invalid_feedback_timeout")
        result = super().__call__(value)
        if not math.isfinite(result) or result != int(result):
            raise vol.Invalid("invalid_feedback_timeout")
        return result


def schema(values, *, include_name=False, version=4):
    fields = {}
    if include_name:
        fields[vol.Required("name", default=values.get("name", "Tank"))] = str
    for key in SOURCE_KEYS:
        fields[vol.Required(key, default=values.get(key, vol.UNDEFINED))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
    fields[vol.Required("max_age_seconds", default=values.get("max_age_seconds", 300))] = (
        selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=10,
                max=86400,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        )
    )
    if not include_name:
        fields[
            vol.Optional(
                "refill_output", description={"suggested_value": values.get("refill_output")}
            )
        ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="switch"))
        fields[
            vol.Optional(
                "commissioned", description={"suggested_value": values.get("commissioned")}
            )
        ] = selector.BooleanSelector()
        fields[
            vol.Optional(
                "feedback_timeout", description={"suggested_value": values.get("feedback_timeout")}
            )
        ] = FeedbackSelector(
            selector.NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="s")
        )
        from .dosing_settings import CONTROL_FIELDS, P3B_CONTROL_FIELDS, Q_KEYS, RANGES

        for key in ("nutrient_output", "acid_output", "circulation_output"):
            fields[vol.Optional(key, description={"suggested_value": values.get(key)})] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="switch"))
            )
        for key in (*CONTROL_FIELDS, *P3B_CONTROL_FIELDS):
            marker = vol.Optional(key, description={"suggested_value": values.get(key)})
            if key.endswith(("commissioned", "confirmed")) or key in (
                "nutrient_commissioned",
                "nutrient_protection_confirmed",
                "report_contract_confirmed",
            ):
                fields[marker] = selector.BooleanSelector()
            elif key.endswith("device_max_on_seconds"):
                fields[marker] = FeedbackSelector(
                    selector.NumberSelectorConfig(min=1, max=86400, step=1)
                )
            elif key.endswith("sample_mode"):
                fields[marker] = selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["reported", "sequence", "timestamp"])
                )
            else:
                fields[marker] = str
        for key, (minimum, maximum, step) in RANGES.items():
            fields[vol.Optional(key, description={"suggested_value": values.get(key)})] = (
                DosingSelector(
                    selector.NumberSelectorConfig(
                        min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
                    )
                )
            )
        for prefix, keys in (
            ("acid_", Q_KEYS),
            ("mix_", ("safe_min_level_m", "flow_timeout_seconds")),
        ):
            for key in keys:
                lo, hi, step = RANGES[key]
                name = prefix + key
                fields[vol.Optional(name, description={"suggested_value": values.get(name)})] = (
                    DosingSelector(
                        selector.NumberSelectorConfig(
                            min=lo, max=hi, step=step, mode=selector.NumberSelectorMode.BOX
                        )
                    )
                )
        for stage in () if version == 5 else STAGES:
            fields[
                vol.Optional(
                    stage + "_weekdays",
                    description={"suggested_value": values.get(stage + "_weekdays", list(DAYS))},
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(DAYS), multiple=True)
            )
    if not include_name and version in (2, 3, 4, 5):
        fields[vol.Optional("flow_plan", default=False)] = selector.BooleanSelector()
    if not include_name and version == 5:
        fields[vol.Optional("recipe_management", default=False)] = selector.BooleanSelector()
    return vol.Schema(fields)


def errors_for(hass, values, *, include_name=False):
    errors = {}
    if include_name and (
        not isinstance(values.get("name"), str)
        or not values["name"].strip()
        or len(values["name"]) > 100
    ):
        errors["name"] = "invalid_name"
    age = values.get("max_age_seconds", 300)
    if (
        isinstance(age, bool)
        or not isinstance(age, (float, int))
        or not 10 <= age <= 86400
        or age != int(age)
    ):
        errors["max_age_seconds"] = "invalid_max_age"
    for key in SOURCE_KEYS:
        entity_id = values.get(key)
        if (
            not isinstance(entity_id, str)
            or not entity_id.startswith("sensor.")
            or hass.states.get(entity_id) is None
        ):
            errors[key] = "invalid_source"
    return errors


class NutricultureConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = errors_for(self.hass, user_input, include_name=True)
            if not errors:
                data = {key: user_input[key] for key in SOURCE_KEYS}
                data.update(
                    name=user_input["name"].strip(),
                    max_age_seconds=int(user_input.get("max_age_seconds", 300)),
                )
                return self.async_create_entry(title=data["name"], data=data)
        return self.async_show_form(
            step_id="user", data_schema=schema(user_input or {}, include_name=True), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NutricultureOptionsFlow()


class NutricultureOptionsFlow(RecipeOptions, OptionsFlow):
    async def async_step_init(self, user_input=None):
        from .control_auth import authorize
        from .dosing_settings import (
            CONTROL_FIELDS,
            DEFAULTS,
            P3B_CONTROL_FIELDS,
            Q_KEYS,
            RANGES,
            SAFETY_KEYS,
        )

        errors = {}
        if user_input and user_input.get("recipe_management") is True:
            return await self.async_step_recipes()
        if user_input and user_input.get("flow_plan") is True:
            return await self.async_step_plan()
        if not hasattr(self, "_revision"):
            self._revision = self.config_entry.options.get("settings_revision", 0)
        if user_input is not None:
            errors = errors_for(self.hass, user_input)
            if not errors:
                try:
                    await authorize(self.hass, Context(user_id=self.context.get("user_id")))
                    tank = self.config_entry.runtime_data
                    async with tank.lock:
                        await authorize(self.hass, Context(user_id=self.context.get("user_id")))
                        config = settings_candidate(self.hass, self.config_entry, user_input)
                        edited_dosing = any(key in user_input for key in RANGES)
                        dosing = None
                        if edited_dosing:
                            dosing = {
                                **DEFAULTS,
                                **self.config_entry.options.get("dosing_parameters", {}),
                                **{key: user_input[key] for key in RANGES if key in user_input},
                            }
                        nutrient_edit = edited_dosing or any(
                            key in user_input
                            for key in (*CONTROL_FIELDS, "nutrient_output", "circulation_output")
                        )
                        acid = {
                            **{k: v for k, v in DEFAULTS.items() if k in Q_KEYS},
                            **self.config_entry.options.get("acid_parameters", {}),
                            **{
                                k: user_input["acid_" + k]
                                for k in Q_KEYS
                                if "acid_" + k in user_input
                            },
                        }
                        mix = {
                            **self.config_entry.options.get("mix_parameters", {}),
                            **{
                                k: user_input["mix_" + k]
                                for k in ("safe_min_level_m", "flow_timeout_seconds")
                                if "mix_" + k in user_input
                            },
                        }
                        new_stage = (
                            any(
                                config.get(
                                    k, False if k.endswith(("commissioned", "confirmed")) else None
                                )
                                != self.config_entry.options.get("control", {}).get(
                                    k, False if k.endswith(("commissioned", "confirmed")) else None
                                )
                                for k in (*P3B_CONTROL_FIELDS, "acid_binding")
                            )
                            or any(
                                "acid_" + k in user_input
                                and acid.get(k)
                                != {
                                    **{k: v for k, v in DEFAULTS.items() if k in Q_KEYS},
                                    **self.config_entry.options.get("acid_parameters", {}),
                                }.get(k)
                                for k in Q_KEYS
                            )
                            or mix != self.config_entry.options.get("mix_parameters", {})
                        )
                        from .manager import _UNSET

                        tank.write_settings(
                            control=config,
                            acid_parameters=acid
                            if new_stage
                            or self.config_entry.options.get("control_contract_version") in (4, 5)
                            else _UNSET,
                            mix_parameters=mix
                            if new_stage
                            or self.config_entry.options.get("control_contract_version") in (4, 5)
                            else _UNSET,
                            safety_parameters={
                                k: user_input.get(
                                    k,
                                    self.config_entry.options.get("safety_parameters", {}).get(
                                        k,
                                        self.config_entry.options.get("dosing_parameters", {}).get(
                                            k, DEFAULTS[k]
                                        ),
                                    ),
                                )
                                for k in SAFETY_KEYS
                            }
                            if new_stage
                            or self.config_entry.options.get("control_contract_version") in (4, 5)
                            else _UNSET,
                            dosing_parameters=dosing,
                            sources={
                                **{key: user_input[key] for key in SOURCE_KEYS},
                                "max_age_seconds": int(user_input.get("max_age_seconds", 300)),
                            },
                            expected_revision=self._revision
                            if nutrient_edit
                            or new_stage
                            or self.config_entry.options.get("control_contract_version") in (4, 5)
                            else None,
                        )
                except ServiceValidationError as err:
                    errors["base"] = str(err)
                else:
                    return self.async_create_entry(title="", data=dict(self.config_entry.options))
        control = self.config_entry.options.get("control", {})
        suggested = {
            **DEFAULTS,
            **self.config_entry.options.get("dosing_parameters", {}),
            **{
                key: control[key]
                for key in (*CONTROL_FIELDS, *P3B_CONTROL_FIELDS)
                if key in control
            },
            **{
                "acid_" + k: v
                for k, v in {
                    **{k: v for k, v in DEFAULTS.items() if k in Q_KEYS},
                    **self.config_entry.options.get("acid_parameters", {}),
                }.items()
            },
            **{
                "mix_" + k: v
                for k, v in self.config_entry.options.get("mix_parameters", {}).items()
            },
            "commissioned": control.get("commissioned", False),
            "feedback_timeout": control.get("feedback_timeout", 10),
        }
        for stage in STAGES:
            suggested[stage + "_weekdays"] = control.get("allowed_weekdays", {}).get(
                stage, list(DAYS)
            )
        for field, binding_key in (
            ("refill_output", "binding"),
            ("nutrient_output", "nutrient_binding"),
            ("acid_output", "acid_binding"),
            ("circulation_output", "circulation_binding"),
        ):
            if control.get(binding_key):
                try:
                    suggested[field] = resolve(self.hass, control[binding_key])
                except ServiceValidationError:
                    pass  # Invalid identities are not suggested as usable targets.
        values = {
            **self.config_entry.data,
            **self.config_entry.options,
            **suggested,
            **(user_input or {}),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=schema(
                values, version=self.config_entry.options.get("control_contract_version", 2)
            ),
            errors=errors,
        )

    async def async_step_plan(self, user_input=None):
        """A draft-only native four-row editor; only explicit Save commits."""
        from copy import deepcopy

        from .control_auth import authorize
        from .flow_settings import default_plan, preview, save, validate_plan
        from .plan_options import parse_plan, plan_schema

        tank = self.config_entry.runtime_data
        if not hasattr(self, "_plan_draft"):
            self._revision = self.config_entry.options.get("settings_revision", 0)
            self._plan_revision = self.config_entry.options.get("flow_plan_revision", 0)
            self._plan_draft = deepcopy(
                self.config_entry.options.get("flow_plan") or default_plan(tank)
            )
            self._plan_days = deepcopy(
                self.config_entry.options.get("control", {}).get(
                    "allowed_weekdays", {s: list(DAYS) for s in STAGES}
                )
            )
        errors = {}
        report = ""
        if user_input is not None:
            action = user_input.get("action", "save")
            if action == "cancel":
                return self.async_abort(reason="plan_cancelled")
            try:
                plan, days = parse_plan(user_input)
                if action.startswith("row_"):
                    index = int(action.split("_")[1])
                    other = index + (1 if action.endswith("down") else -1)
                    plan["rows"][index], plan["rows"][other] = (
                        plan["rows"][other],
                        plan["rows"][index],
                    )
                plan, days = validate_plan(plan, days)
                self._plan_draft, self._plan_days = plan, days
                await authorize(self.hass, Context(user_id=self.context.get("user_id")))
                async with tank.lock:
                    await authorize(self.hass, Context(user_id=self.context.get("user_id")))
                    from homeassistant.config_entries import ConfigEntryState

                    if (
                        not tank.active
                        or self.config_entry.runtime_data is not tank
                        or self.config_entry.state is not ConfigEntryState.LOADED
                    ):
                        raise ServiceValidationError("entry_not_loaded")
                    if action == "save":
                        save(
                            tank,
                            dict(
                                expected_revision=self._revision,
                                expected_flow_plan_revision=self._plan_revision,
                                flow_plan=plan,
                                allowed_weekdays=days,
                            ),
                        )
                        return self.async_create_entry(
                            title="", data=dict(self.config_entry.options)
                        )
                    report = "\n".join(
                        day
                        + ": "
                        + ", ".join(
                            r["stage"] + "=" + r["eligibility"]
                            for r in preview(tank, plan, days, day)["rows"]
                        )
                        for day in DAYS
                    )
            except ServiceValidationError as err:
                code = str(err)
                errors["base"] = (
                    code
                    if code
                    in {
                        "invalid_flow_plan",
                        "invalid_flow_condition",
                        "invalid_weekdays",
                        "settings_conflict",
                        "settings_schema_mismatch",
                        "control_busy",
                        "entry_not_loaded",
                    }
                    else "invalid_flow_plan"
                )
        return self.async_show_form(
            step_id="plan",
            data_schema=plan_schema(self._plan_draft, self._plan_days),
            errors=errors,
            description_placeholders={"preview": report},
        )
