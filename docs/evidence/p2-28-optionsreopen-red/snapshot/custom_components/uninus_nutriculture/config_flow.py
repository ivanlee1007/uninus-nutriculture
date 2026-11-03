"""Native config and source-binding options flows."""

import math

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.exceptions import ServiceValidationError

from .control_settings import DAYS, STAGES, settings_candidate

from .const import DOMAIN, SOURCE_KEYS


class FeedbackSelector(selector.NumberSelector):
    """Keep native selector rendering while rejecting unsafe coercions."""

    def __call__(self, value):
        if isinstance(value, bool):
            raise vol.Invalid("invalid_feedback_timeout")
        result = super().__call__(value)
        if not math.isfinite(result) or result != int(result):
            raise vol.Invalid("invalid_feedback_timeout")
        return result


def schema(values, *, include_name=False):
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
        fields[vol.Optional("refill_output")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="switch")
        )
        fields[vol.Optional("commissioned")] = selector.BooleanSelector()
        fields[vol.Optional("feedback_timeout")] = FeedbackSelector(
            selector.NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="s")
        )
        for stage in STAGES:
            fields[vol.Optional(stage + "_weekdays")] = selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(DAYS), multiple=True)
            )
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


class NutricultureOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = errors_for(self.hass, user_input)
            if not errors:
                # Read latest options at submission, preserving intervening Number writes.
                options = {
                    **self.config_entry.options,
                    **{key: user_input[key] for key in SOURCE_KEYS},
                    "max_age_seconds": int(user_input.get("max_age_seconds", 300)),
                }
                try:
                    options["control"] = settings_candidate(self.hass, self.config_entry, user_input)
                except ServiceValidationError as err:
                    errors["base"] = str(err)
                else:
                    return self.async_create_entry(title="", data=options)
        values = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        return self.async_show_form(step_id="init", data_schema=schema(values), errors=errors)
