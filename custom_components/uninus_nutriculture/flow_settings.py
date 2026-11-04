"""Schema5 closed plan grammar, atomic namespace writer and dry-run preview."""

import math
from copy import deepcopy

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .control_auth import authorize
from .control_settings import DAYS, STAGES

RULES = ("flow_start", "after_previous_started", "after_previous_finished")


def validate_plan(plan, days):
    def integer(value, low, high):
        return type(value) is int and low <= value <= high

    if (
        not isinstance(plan, dict)
        or set(plan) != {"rows", "run_timeout_seconds"}
        or not integer(plan["run_timeout_seconds"], 1, 86400)
    ):
        raise ServiceValidationError("invalid_flow_plan")
    rows = plan["rows"]
    if not isinstance(rows, list) or len(rows) != 4:
        raise ServiceValidationError("invalid_flow_plan")
    stages = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {
            "stage",
            "start_rule",
            "delay_seconds",
            "condition",
            "wait_timeout_seconds",
        }:
            raise ServiceValidationError("invalid_flow_plan")
        if (
            row["stage"] not in STAGES
            or row["start_rule"] not in RULES
            or (i == 0 and row["start_rule"] != "flow_start")
            or not integer(row["delay_seconds"], 0, 86400)
            or not integer(row["wait_timeout_seconds"], 1, 86400)
        ):
            raise ServiceValidationError("invalid_flow_plan")
        stages.append(row["stage"])
        c = row["condition"]
        if c is not None:
            if (
                not isinstance(c, dict)
                or set(c) != {"source", "operator", "value"}
                or c["source"] not in ("level", "ph", "ec")
                or c["operator"] not in ("gte", "lte")
                or type(c["value"]) not in (int, float)
                or not math.isfinite(c["value"])
                or not 0 <= c["value"] <= {"level": 10, "ph": 14, "ec": 20}[c["source"]]
            ):
                raise ServiceValidationError("invalid_flow_condition")
    if set(stages) != set(STAGES):
        raise ServiceValidationError("invalid_flow_plan")
    if (
        not isinstance(days, dict)
        or set(days) != set(STAGES)
        or any(
            not isinstance(v, list) or any(d not in DAYS for d in v) or len(v) != len(set(v))
            for v in days.values()
        )
    ):
        raise ServiceValidationError("invalid_weekdays")
    return deepcopy(plan), deepcopy(days)


def default_plan(tank):
    o = tank.entry.options
    upper = (
        tank.parameters["refill_timeout"] * 60
        + sum(
            o.get(k + "_parameters", {}).get("flow_timeout_seconds", 5400)
            for k in ("dosing", "acid", "mix")
        )
        + 4 * 300
    )
    return {
        "rows": [
            dict(
                stage=s,
                start_rule="flow_start" if i == 0 else "after_previous_finished",
                delay_seconds=0,
                condition=None,
                wait_timeout_seconds=300,
            )
            for i, s in enumerate(STAGES)
        ],
        "run_timeout_seconds": min(86400, int(upper)),
    }


def source(tank, key):
    s = tank.hass.states.get(tank.sources[key])
    return source_state(tank, key, s)


def source_state(tank, key, s):
    """Validate a captured report as strictly as the current state."""
    units = {"level": ("m",), "ph": (None, "", "pH"), "ec": ("mS/cm",)}
    try:
        v = float(s.state)
        age = (dt_util.utcnow() - s.last_reported).total_seconds()
        if (
            not math.isfinite(v)
            or s.attributes.get("unit_of_measurement") not in units[key]
            or not 0 <= age <= tank.entry.options.get("max_age_seconds", 300)
        ):
            return None
        return v
    except ValueError, TypeError, AttributeError:
        return None


def dependency_ready(rule, result, started):
    """Three-state real anchor truth, shared by runtime and Preview."""
    if rule == "flow_start":
        return True
    if rule == "after_previous_started":
        return True if started else False if result else None
    if result in ("completed", "skipped_disabled", "skipped_weekday"):
        return True
    return False if result else None


def reachable_refill(tank, plan, days, day, enabled, records=None, blocked=None):
    """Walk only the four fixed preceding-row anchors; no arbitrary DAG."""
    records = records or {}
    blocked = set(blocked or ())
    possible_started, possible_finished = False, False
    level = source(tank, "level")
    for row in plan["rows"]:
        name = row["stage"]
        r = records.get(name, {})
        rule = row["start_rule"]
        anchor = rule == "flow_start" or (
            possible_started if rule == "after_previous_started" else possible_finished
        )
        result, started = r.get("result"), r.get("started_at") is not None
        if result:
            possible_started = started
            possible_finished = dependency_ready("after_previous_finished", result, started) is True
            if name == "refill":
                return False
            continue
        if name == "refill":
            return bool(
                anchor
                and enabled[name]
                and day in days[name]
                and all(source(tank, k) is not None for k in ("level", "ph", "ec"))
            )
        skip = not enabled[name] or day not in days[name]
        minimum = tank.entry.options.get(
            ("dosing" if name == "nutrient" else name) + "_parameters", {}
        ).get("safe_min_level_m", 0.5)
        unsafe = level is None or level < minimum or (name == "nutrient" and level == minimum)
        possible_started = started or (anchor and not skip and name not in blocked and not unsafe)
        possible_finished = anchor and (skip or possible_started)
    return False


def preview(tank, plan, days, day):
    rows = []
    enabled = {s: bool(getattr(tank.control, s)) for s in STAGES}
    refill_reachable = reachable_refill(tank, plan, days, day, enabled)
    for row in plan["rows"]:
        name = row["stage"]
        previous = rows[-1] if rows else None
        eligibility = "eligible"
        uncertainty = []
        prior = previous["eligibility"] if previous else "eligible"
        prior_result = None if prior == "eligible" else prior
        if (
            previous
            and dependency_ready(row["start_rule"], prior_result, prior == "eligible") is False
        ):
            eligibility = "blocked_dependency"
        elif not enabled[name]:
            eligibility = "skipped_disabled"
        elif day not in days[name]:
            eligibility = "skipped_weekday"
        required = ["level"] if name == "mix" else ["level", "ph", "ec"]
        if row["condition"]:
            required.append(row["condition"]["source"])
        if eligibility == "eligible":
            if any(source(tank, k) is None for k in required):
                eligibility = "blocked_safety"
            elif name != "refill":
                minimum = tank.entry.options.get(
                    ("dosing" if name == "nutrient" else name) + "_parameters", {}
                ).get("safe_min_level_m", 0.5)
                if source(tank, "level") < minimum or (
                    name == "nutrient" and source(tank, "level") == minimum
                ):
                    if refill_reachable:
                        uncertainty.append("level_waits_for_refill")
                    else:
                        eligibility = "blocked_safety"
        offset = row["delay_seconds"] if row["start_rule"] == "flow_start" else None
        if (
            row["start_rule"] == "after_previous_started"
            and previous
            and previous["earliest_offset_seconds"] is not None
            and previous["eligibility"] == "eligible"
        ):
            offset = previous["earliest_offset_seconds"] + row["delay_seconds"]
        if row["start_rule"] == "after_previous_finished":
            uncertainty.append("previous_finish_unknown")
        if name in ("refill", "nutrient", "acid"):
            uncertainty.append("sensor_duration_unknown")
        if name in ("nutrient", "acid"):
            uncertainty.append("chemical_resource_wait_possible")
        if row["condition"]:
            uncertainty.append("condition_revalidated_at_admission")
        rows.append(
            dict(
                stage=name,
                eligibility=eligibility,
                earliest_offset_seconds=offset,
                uncertainties=uncertainty,
            )
        )
    return dict(
        settings_revision=tank.entry.options.get("settings_revision", 0),
        flow_plan_revision=tank.entry.options.get("flow_plan_revision", 0),
        weekday=day,
        rows=rows,
        warnings=["admission_weekday_runtime_authoritative", "global_deadline_may_limit_stages"],
    )


def save(tank, payload):
    o = tank.entry.options
    if o.get("control_contract_version", 2) not in (2, 3, 4, 5) or not o.get("control"):
        raise ServiceValidationError("settings_schema_mismatch")
    if payload["expected_revision"] != o.get("settings_revision", 0) or payload[
        "expected_flow_plan_revision"
    ] != o.get("flow_plan_revision", 0):
        raise ServiceValidationError("settings_conflict")
    plan, days = validate_plan(payload["flow_plan"], payload["allowed_weekdays"])
    transition = o.get("control_contract_version") != 5
    if transition and (tank.control.master or tank.control.running or tank.control.leases):
        raise ServiceValidationError("control_busy")
    changed = (
        transition or plan != o.get("flow_plan") or days != o["control"].get("allowed_weekdays")
    )
    if changed:
        candidate = {
            **o,
            "control_contract_version": 5,
            "flow_plan": plan,
            "flow_plan_revision": o.get("flow_plan_revision", 0) + 1,
            "settings_revision": o.get("settings_revision", 0) + 1,
            "control": {**o["control"], "allowed_weekdays": days},
        }
        tank.hass.config_entries.async_update_entry(tank.entry, options=candidate)
        tank.publish()
    o = tank.entry.options
    return dict(
        applied=True,
        settings_revision=o.get("settings_revision", 0),
        flow_plan_revision=o.get("flow_plan_revision", 0),
        flow_plan=deepcopy(o["flow_plan"]),
        allowed_weekdays=deepcopy(o["control"]["allowed_weekdays"]),
    )


def register(hass):
    def revision(v):
        if type(v) is not int or not 0 <= v <= 9007199254740991:
            raise vol.Invalid("invalid_revision")
        return v

    async def handler(call):
        await authorize(hass, call.context)
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if not entry or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("entry_not_loaded")
        tank = entry.runtime_data
        async with tank.lock:
            await authorize(hass, call.context)
            if (
                not tank.active
                or entry.runtime_data is not tank
                or entry.state is not ConfigEntryState.LOADED
            ):
                raise ServiceValidationError("entry_not_loaded")
            if call.service == "apply_flow_plan_v5":
                result = save(tank, call.data)
            else:
                o = entry.options
                if o.get("control_contract_version") != 5:
                    raise ServiceValidationError("settings_schema_mismatch")
                if call.data["expected_revision"] != o.get("settings_revision", 0) or call.data[
                    "expected_flow_plan_revision"
                ] != o.get("flow_plan_revision", 0):
                    raise ServiceValidationError("settings_conflict")
                p, d = validate_plan(call.data["flow_plan"], call.data["allowed_weekdays"])
                result = preview(tank, p, d, call.data["weekday"])
        return result if call.return_response else None

    fields = {
        vol.Required("config_entry_id"): str,
        vol.Required("expected_revision"): revision,
        vol.Required("expected_flow_plan_revision"): revision,
        vol.Required("flow_plan"): dict,
        vol.Required("allowed_weekdays"): dict,
    }
    for name in ("apply_flow_plan_v5", "preview_flow_plan_v5"):
        schema = dict(fields)
        if name.startswith("preview"):
            schema[vol.Required("weekday")] = vol.In(DAYS)
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=vol.Schema(schema),
            supports_response=SupportsResponse.OPTIONAL,
        )
