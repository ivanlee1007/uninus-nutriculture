"""Exact schema4 public projection. No actuator effects."""

from homeassistant.exceptions import ServiceValidationError

from .control_settings import DAYS, STAGES, resolve
from .dosing_settings import DEFAULTS, SAFETY_KEYS


def snapshot_v4(tank, base, targets):
    c = tank.control
    options = tank.entry.options
    config = options.get("control", {})
    capabilities = {
        "refill": bool(config.get("commissioned")),
        "nutrient": c.supports_nutrient,
        "acid": c.supports_acid,
        "mix": bool(getattr(c, "supports_mix", False)),
    }
    states = {}
    for name in STAGES:
        if not capabilities[name]:
            states[name] = "unsupported"
            continue
        stage = getattr(c, name + "_stage", None)
        if stage and stage.result is not None and not stage.owns_io:
            states[name] = stage.result
        elif c.run_stage == name and c.running:
            states[name] = (
                "stopping"
                if c.flow_state == "stopping"
                else "starting"
                if c.flow_state == "starting"
                else "running"
            )
        elif c.run_stage and c.run_stage != name:
            states[name] = "skipped_disabled"
        elif name == "refill" and c.run_stage == name:
            states[name] = (
                c.flow_state if c.flow_state in ("completed", "aborted", "fault") else "idle"
            )
        else:
            states[name] = "idle"
    outputs = {}
    for role in ("nutrient", "acid", "circulation"):
        try:
            state = tank.hass.states.get(resolve(tank.hass, config.get(role + "_binding")))
            outputs[role] = state.state if state and state.state in ("on", "off") else "unknown"
        except ServiceValidationError:
            outputs[role] = "unknown"
    zero = {"pulse_count": 0, "reserved_on_seconds": 0, "stable_count": 0}
    return {
        **base,
        "reasons": list(
            dict.fromkeys(
                [*base.get("reasons", []), *(["ph_high_alarm"] if c.ph_high_alarm_active else [])]
            )
        ),
        "schema_version": 4,
        "mode": "control",
        "capabilities": capabilities,
        "control_entities": targets,
        "allowed_weekdays": config.get("allowed_weekdays", {s: list(DAYS) for s in STAGES}),
        "stage_states": states,
        "flow_state": c.flow_state,
        "fault": c.fault,
        "run_id": c.run_id,
        "settings_target": {
            "config_entry_id": tank.entry.entry_id,
            "service": "apply_control_settings_v4",
        },
        "settings_revision": options.get("settings_revision", 0),
        "dosing_parameters": dict(options["dosing_parameters"])
        if capabilities["nutrient"]
        else None,
        "acid_parameters": dict(options["acid_parameters"]) if capabilities["acid"] else None,
        "mix_parameters": dict(options["mix_parameters"]) if capabilities["mix"] else None,
        "safety_parameters": dict(
            options.get("safety_parameters", {k: DEFAULTS[k] for k in SAFETY_KEYS})
        ),
        "nutrient_phase": c.nutrient_stage.phase,
        "acid_phase": c.acid_stage.phase,
        "dose_progress": dict(c.nutrient_stage.progress or zero),
        "acid_progress": dict(c.acid_stage.progress or zero),
        "output_states": outputs,
    }
