"""P2 native configuration and registry-bound output identity."""

from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
STAGES = ("refill", "nutrient", "acid", "mix")


def identity(row):
    return {
        "registry_id": row.id,
        "platform": row.platform,
        "unique_id": row.unique_id,
        "config_entry_id": row.config_entry_id,
    }


def resolve(hass, binding):
    if not binding:
        raise ServiceValidationError("output_unbound")
    row = next(
        (
            row
            for row in er.async_get(hass).entities.values()
            if row.id == binding.get("registry_id")
        ),
        None,
    )
    if (
        row is None
        or row.disabled_by
        or row.domain != "switch"
        or row.platform == DOMAIN
        or identity(row) != binding
    ):
        raise ServiceValidationError("output_identity_invalid")
    return row.entity_id


def settings_candidate(hass, entry, values):
    old = dict(entry.options.get("control", {}))
    candidate = dict(old)
    if "refill_output" in values:
        row = er.async_get(hass).async_get(values["refill_output"])
        if row is None or row.disabled_by or row.domain != "switch" or row.platform == DOMAIN:
            raise ServiceValidationError("output_identity_invalid")
        binding = identity(row)
        for other in hass.config_entries.async_entries(DOMAIN):
            if other.entry_id != entry.entry_id:
                owned = other.options.get("control", {}).get("binding")
                if owned and (
                    owned.get("registry_id") == row.id
                    or (owned.get("platform"), owned.get("unique_id"))
                    == (row.platform, row.unique_id)
                ):
                    raise ServiceValidationError("output_already_owned")
        candidate["binding"] = binding
    if "commissioned" in values:
        candidate["commissioned"] = values["commissioned"]
    candidate.setdefault("commissioned", False)
    if "feedback_timeout" in values:
        candidate["feedback_timeout"] = values["feedback_timeout"]
    candidate.setdefault("feedback_timeout", 10)
    days = dict(old.get("allowed_weekdays", {key: list(DAYS) for key in STAGES}))
    for stage in STAGES:
        if stage + "_weekdays" in values:
            days[stage] = list(dict.fromkeys(values[stage + "_weekdays"]))
    candidate["allowed_weekdays"] = days
    if candidate.get("commissioned"):
        resolve(hass, candidate.get("binding"))
    if candidate.get("binding") != old.get("binding") or candidate.get("commissioned") != old.get(
        "commissioned", False
    ):
        controller = getattr(getattr(entry, "runtime_data", None), "control", None)
        if controller and (controller.master or controller.running):
            raise ServiceValidationError("control_busy")
        for binding in (old.get("binding"), candidate.get("binding")):
            if binding:
                target = resolve(hass, binding)
                state = hass.states.get(target)
                if state is None or state.state != "off":
                    raise ServiceValidationError("output_not_off")
    from .dosing_settings import CONTROL_FIELDS, P3B_CONTROL_FIELDS

    for field, key in (
        ("nutrient_output", "nutrient_binding"),
        ("acid_output", "acid_binding"),
        ("circulation_output", "circulation_binding"),
    ):
        if field in values:
            row = er.async_get(hass).async_get(values[field])
            if row is None:
                raise ServiceValidationError("output_identity_invalid")
            candidate[key] = identity(row)
            resolve(hass, candidate[key])
    for key in (*CONTROL_FIELDS, *P3B_CONTROL_FIELDS):
        if key in values:
            candidate[key] = values[key]
    bindings = [
        candidate.get(key)
        for key in ("binding", "nutrient_binding", "acid_binding", "circulation_binding")
    ]
    owned = set()
    for binding in bindings:
        if not binding:
            continue
        target = resolve(hass, binding)
        resource = (binding["platform"], binding["unique_id"])
        if resource in owned:
            raise ServiceValidationError("output_already_owned")
        owned.add(resource)
        for other in hass.config_entries.async_entries(DOMAIN):
            if other.entry_id == entry.entry_id:
                continue
            other_control = other.options.get("control", {})
            for key in ("binding", "nutrient_binding", "acid_binding", "circulation_binding"):
                other_binding = other_control.get(key)
                if other_binding and (
                    other_binding.get("registry_id") == binding["registry_id"]
                    or (other_binding.get("platform"), other_binding.get("unique_id")) == resource
                ):
                    raise ServiceValidationError("output_already_owned")
    if candidate.get("nutrient_commissioned"):
        resolve(hass, candidate.get("nutrient_binding"))
        resolve(hass, candidate.get("circulation_binding"))
    if candidate.get("acid_commissioned"):
        resolve(hass, candidate.get("acid_binding"))
        resolve(hass, candidate.get("circulation_binding"))
    if candidate.get("mix_commissioned"):
        resolve(hass, candidate.get("circulation_binding"))
    protected = (
        "binding",
        "commissioned",
        "nutrient_binding",
        "circulation_binding",
        "acid_binding",
        *CONTROL_FIELDS,
        *P3B_CONTROL_FIELDS,
    )
    source_change = any(
        key in values and values[key] != entry.options.get(key, entry.data.get(key))
        for key in ("ph", "ec", "level", "max_age_seconds")
    )
    if source_change or any(candidate.get(key) != old.get(key) for key in protected):
        ensure_stopped(hass, entry, old, candidate)
    return candidate


def ensure_stopped(hass, entry, old, candidate):
    """No hidden OFF: old and new outputs must already be known OFF."""
    controller = getattr(getattr(entry, "runtime_data", None), "control", None)
    if controller and (
        controller.master
        or controller.running
        or any(
            task is not None and not task.done()
            for task in (
                getattr(controller, "on_task", None),
                getattr(controller, "off_task", None),
            )
        )
    ):
        raise ServiceValidationError("control_busy")
    for config in (old, candidate):
        for key in ("binding", "nutrient_binding", "acid_binding", "circulation_binding"):
            if config.get(key):
                state = hass.states.get(resolve(hass, config[key]))
                if state is None or state.state != "off":
                    raise ServiceValidationError("output_not_off")
