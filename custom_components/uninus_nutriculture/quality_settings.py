"""Closed quality policy grammar. Virtual defaults never write options."""

from copy import deepcopy

from homeassistant.exceptions import ServiceValidationError

MAX_REVISION = 9007199254740991
STAGES = ("refill", "nutrient", "acid", "mix")
KEYS = {
    "enabled",
    "stable_samples",
    "stable_interval_seconds",
    "stable_duration_seconds",
    "permit_ttl_seconds",
    "required_stages",
    "sources",
}


def revision(v):
    return type(v) is int and 0 <= v <= MAX_REVISION


def validate(policy):
    bad = ServiceValidationError("invalid_quality_policy")
    if not isinstance(policy, dict) or set(policy) != KEYS or type(policy["enabled"]) is not bool:
        raise bad
    for k in (
        "stable_samples",
        "stable_interval_seconds",
        "stable_duration_seconds",
        "permit_ttl_seconds",
    ):
        v = policy[k]
        if type(v) is not int or not 1 <= v <= (100 if k == "stable_samples" else 86400):
            raise bad
    stages = policy["required_stages"]
    if (
        not isinstance(stages, list)
        or not stages
        or any(type(s) is not str or s not in STAGES for s in stages)
        or len(set(stages)) != len(stages)
    ):
        raise bad
    sources = policy["sources"]
    if not isinstance(sources, dict) or set(sources) != {"ph", "ec", "level"}:
        raise bad
    for row in sources.values():
        if not isinstance(row, dict) or set(row) != {
            "mode",
            "attribute",
            "report_contract_confirmed",
        }:
            raise bad
        m, a, c = row["mode"], row["attribute"], row["report_contract_confirmed"]
        if (
            m not in ("reported", "sequence", "timestamp")
            or type(c) is not bool
            or (policy["enabled"] and not c)
        ):
            raise bad
        if (m == "reported" and a is not None) or (
            m != "reported" and (type(a) is not str or not 1 <= len(a) <= 128)
        ):
            raise bad
    return deepcopy(policy)


def read(tank):
    o = tank.entry.options
    if "quality_policy" in o:
        row = o["quality_policy"]
        if (
            not isinstance(row, dict)
            or set(row) != KEYS | {"schema_version", "revision"}
            or type(row["schema_version"]) is not int
            or row["schema_version"] != 1
            or not revision(row["revision"])
        ):
            raise ServiceValidationError("settings_schema_mismatch")
        return validate({k: v for k, v in row.items() if k in KEYS}), row["revision"]
    age = o.get("max_age_seconds", tank.entry.data.get("max_age_seconds", 300))
    age = max(1, min(86400, int(age)))
    return dict(
        enabled=False,
        stable_samples=8,
        stable_interval_seconds=300,
        stable_duration_seconds=2100,
        permit_ttl_seconds=age,
        required_stages=list(STAGES),
        sources={
            k: dict(mode="reported", attribute=None, report_contract_confirmed=False)
            for k in ("ph", "ec", "level")
        },
    ), 0
