"""Schema5 authoritative projection, preserving schema4's untouched wire."""

from copy import deepcopy

from .control_settings import resolve
from .flow_settings import default_plan
from .p3b_projection import snapshot_v4


def snapshot_v5(tank, base, targets):
    result = snapshot_v4(tank, base, targets)
    flow = tank.control.flow
    flow.refresh()
    o = tank.entry.options
    result.update(
        schema_version=5,
        flow_plan=deepcopy(o.get("flow_plan", default_plan(tank))),
        flow_plan_revision=o.get("flow_plan_revision", 0),
        flow_plan_target=dict(
            config_entry_id=tank.entry.entry_id,
            service="apply_flow_plan_v5",
            preview_service="preview_flow_plan_v5",
        ),
        run_plan=deepcopy(flow.run_plan),
        step_runtime=deepcopy(flow.records),
    )
    result["settings_target"]["service"] = "apply_control_settings_v5"
    try:
        state = tank.hass.states.get(resolve(tank.hass, o.get("control", {}).get("binding")))
        result["output_states"]["refill"] = (
            state.state if state and state.state in ("on", "off") else "unknown"
        )
    except Exception:
        result["output_states"]["refill"] = "unknown"
    if flow.run_plan:
        for s, r in flow.records.items():
            p = r["phase"]
            result["stage_states"][s] = r["result"] or (
                p
                if p in ("waiting_delay", "waiting_condition", "waiting_resource", "starting")
                else "stopping"
                if p == "stopping"
                else "running"
                if p
                else "idle"
            )
    return result
