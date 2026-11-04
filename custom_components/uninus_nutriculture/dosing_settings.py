"""Nutrient settings validation; engineering limits, not physical certification."""

import math
import re
from decimal import Decimal

from homeassistant.exceptions import ServiceValidationError

DEFAULTS = {
    "post_mix_seconds": 300,
    "sample_wait_timeout_seconds": 600,
    "stable_samples": 8,
    "stable_interval_seconds": 300,
    "flow_timeout_seconds": 5400,
    "ph_danger_low": 3.8,
    "ec_danger_high": 1.3,
    "ph_high_alarm": 6.8,
    "ph_high_alarm_seconds": 600,
}
RANGES = {
    "safe_min_level_m": (0, 10, 0.01),
    "pulse_seconds": (1, 86400, 1),
    "max_total_on_seconds": (1, 86400, 1),
    "max_pulses": (1, 1000, 1),
    "post_mix_seconds": (1, 86400, 1),
    "sample_wait_timeout_seconds": (1, 86400, 1),
    "stable_samples": (1, 100, 1),
    "stable_interval_seconds": (1, 86400, 1),
    "flow_timeout_seconds": (1, 86400, 1),
    "ph_danger_low": (0, 14, 0.1),
    "ec_danger_high": (0, 100, 0.01),
    "ph_high_alarm": (0, 14, 0.1),
    "ph_high_alarm_seconds": (1, 86400, 1),
}
SAFETY_KEYS = tuple(DEFAULTS)[5:]
Q_KEYS = tuple(key for key in RANGES if key not in SAFETY_KEYS)
P3B_CONTROL_FIELDS = (
    "acid_commissioned",
    "acid_device_max_on_seconds",
    "acid_protection_confirmed",
    "acid_alias_notes",
    "acid_sample_mode",
    "acid_sample_attribute",
    "acid_report_contract_confirmed",
    "mix_commissioned",
    "circulation_device_max_on_seconds",
    "circulation_protection_confirmed",
    "circulation_alias_notes",
)

CONTROL_FIELDS = (
    "nutrient_commissioned",
    "nutrient_protection_confirmed",
    "device_max_on_seconds",
    "alias_notes",
    "sample_mode",
    "sample_attribute",
    "report_contract_confirmed",
)


def numeric(value, minimum, maximum, step):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
        or (Decimal(str(value)) - Decimal(str(minimum))) % Decimal(str(step))
    ):
        raise ServiceValidationError("invalid_dosing_parameter")


def validate_dosing(parameters, dosing, control):
    if set(dosing) != set(RANGES):
        raise ServiceValidationError("invalid_dosing_parameters")
    for key, value in dosing.items():
        numeric(value, *RANGES[key])
    for key in (
        "nutrient_commissioned",
        "nutrient_protection_confirmed",
        "report_contract_confirmed",
    ):
        if key in control and type(control[key]) is not bool:
            raise ServiceValidationError("invalid_commissioning")
    if not control.get("nutrient_commissioned"):
        return
    numeric(control.get("device_max_on_seconds"), 1, 86400, 1)
    if (
        not control.get("nutrient_protection_confirmed")
        or not isinstance(control.get("alias_notes"), str)
        or not control["alias_notes"].strip()
        or len(control["alias_notes"]) > 512
    ):
        raise ServiceValidationError("nutrient_protection_unconfirmed")
    mode = control.get("sample_mode")
    if mode == "reported":
        if control.get("report_contract_confirmed") is not True:
            raise ServiceValidationError("sample_contract_unconfirmed")
    elif mode not in ("sequence", "timestamp") or not re.fullmatch(
        r"[A-Za-z0-9_]{1,64}", control.get("sample_attribute", "")
    ):
        raise ServiceValidationError("invalid_sample_contract")
    deadline = min(parameters["ec_timeout"] * 60, dosing["flow_timeout_seconds"])
    if (
        dosing["pulse_seconds"]
        > min(control["device_max_on_seconds"], dosing["max_total_on_seconds"])
        or dosing["pulse_seconds"]
        + control.get("feedback_timeout", 10)
        + dosing["post_mix_seconds"]
        + dosing["stable_interval_seconds"] * (dosing["stable_samples"] - 1)
        > deadline
        or dosing["ec_danger_high"] <= parameters["ec_high"]
        or dosing["ph_danger_low"] >= parameters["ph_low"]
    ):
        raise ServiceValidationError("invalid_dosing_relationship")
