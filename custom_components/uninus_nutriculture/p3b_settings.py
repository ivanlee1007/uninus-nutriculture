"""Schema4 settings and commissioning without fabricated physical limits."""

from homeassistant.exceptions import ServiceValidationError

from .dosing_settings import DEFAULTS, Q_KEYS, RANGES, SAFETY_KEYS, numeric, validate_dosing


def validate_v4(params, candidate, control, acid=None, mix=None, safety=None):
    old_dosing = candidate.get("dosing_parameters", {})
    s = dict(
        safety
        if safety is not None
        else candidate.get(
            "safety_parameters", {k: old_dosing.get(k, DEFAULTS[k]) for k in SAFETY_KEYS}
        )
    )
    if set(s) != set(SAFETY_KEYS):
        raise ServiceValidationError("invalid_dosing_parameters")
    for k, v in s.items():
        numeric(v, *RANGES[k])
    if s["ph_danger_low"] >= params["ph_low"] or s["ec_danger_high"] <= params["ec_high"]:
        raise ServiceValidationError("invalid_dosing_relationship")
    candidate["safety_parameters"] = s
    candidate["dosing_parameters"] = {**old_dosing, **s}
    for name, incoming, keys in (
        ("acid", acid, Q_KEYS),
        ("mix", mix, ("safe_min_level_m", "flow_timeout_seconds")),
    ):
        values = dict(incoming if incoming is not None else candidate.get(name + "_parameters", {}))
        if not set(values) <= set(keys):
            raise ServiceValidationError("invalid_dosing_parameters")
        for k, v in values.items():
            numeric(v, *RANGES[k])
        if control.get(name + "_commissioned"):
            if set(values) != set(keys):
                raise ServiceValidationError("invalid_dosing_parameters")
            numeric(control.get("circulation_device_max_on_seconds"), 1, 86400, 1)
            if (
                not control.get("circulation_protection_confirmed")
                or not str(control.get("circulation_alias_notes", "")).strip()
            ):
                raise ServiceValidationError("nutrient_protection_unconfirmed")
            f = control.get("feedback_timeout", 10)
            c = control["circulation_device_max_on_seconds"]
            if name == "acid":
                adapted = {
                    **control,
                    "nutrient_commissioned": True,
                    **{
                        k: control.get("acid_" + k)
                        for k in (
                            "device_max_on_seconds",
                            "sample_mode",
                            "sample_attribute",
                            "report_contract_confirmed",
                            "alias_notes",
                        )
                    },
                    "nutrient_protection_confirmed": control.get("acid_protection_confirmed"),
                }
                validate_dosing(
                    {**params, "ec_timeout": params["ph_timeout"]}, {**values, **s}, adapted
                )
                if values["pulse_seconds"] + f > control["acid_device_max_on_seconds"] or values[
                    "pulse_seconds"
                ] + 2 * f + values["post_mix_seconds"] > min(
                    c, values["flow_timeout_seconds"], params["ph_timeout"] * 60
                ):
                    raise ServiceValidationError("invalid_dosing_relationship")
            elif params["mix_duration"] * 60 + 2 * f > min(c, values["flow_timeout_seconds"]):
                raise ServiceValidationError("invalid_dosing_relationship")
        candidate[name + "_parameters"] = values
    candidate["control_contract_version"] = 4
