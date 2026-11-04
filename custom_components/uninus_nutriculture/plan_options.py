"""Native non-JSON plan field adapters; shared validator remains authoritative."""

import voluptuous as vol
from homeassistant.helpers import selector

from .config_flow import DosingSelector, FeedbackSelector
from .control_settings import DAYS, STAGES
from .flow_settings import RULES


def plan_schema(plan, days):
    fields = {}

    def field(name, value, validator):
        fields[vol.Required(name, description={"suggested_value": value})] = validator

    def select(options, multiple=False):
        return selector.SelectSelector(
            selector.SelectSelectorConfig(options=list(options), multiple=multiple)
        )

    def number(low, high, integer=True):
        cls = FeedbackSelector if integer else DosingSelector
        return cls(
            selector.NumberSelectorConfig(
                min=low, max=high, step=1 if integer else 0.01, mode=selector.NumberSelectorMode.BOX
            )
        )

    field("run_timeout_seconds", plan["run_timeout_seconds"], number(1, 86400))
    for i, row in enumerate(plan["rows"]):
        prefix = "row_" + str(i) + "_"
        field(prefix + "stage", row["stage"], select(STAGES))
        field(prefix + "start_rule", row["start_rule"], select(RULES))
        field(prefix + "delay_seconds", row["delay_seconds"], number(0, 86400))
        field(prefix + "wait_timeout_seconds", row["wait_timeout_seconds"], number(1, 86400))
        condition = row["condition"]
        field(
            prefix + "condition_source",
            condition["source"] if condition else "none",
            select(("none", "level", "ph", "ec")),
        )
        field(
            prefix + "condition_operator",
            condition["operator"] if condition else "gte",
            select(("gte", "lte")),
        )
        field(
            prefix + "condition_value", condition["value"] if condition else 0, number(0, 20, False)
        )
        field(prefix + "weekdays", days[row["stage"]], select(DAYS, True))
    field(
        "action",
        "save",
        select(
            (
                "save",
                "preview",
                "cancel",
                "row_0_down",
                "row_1_up",
                "row_1_down",
                "row_2_up",
                "row_2_down",
                "row_3_up",
            )
        ),
    )
    return vol.Schema(fields)


def parse_plan(values):
    rows, days = [], {}
    for i in range(4):
        prefix = "row_" + str(i) + "_"
        stage = values[prefix + "stage"]
        source = values[prefix + "condition_source"]
        rows.append(
            dict(
                stage=stage,
                start_rule=values[prefix + "start_rule"],
                delay_seconds=int(values[prefix + "delay_seconds"]),
                wait_timeout_seconds=int(values[prefix + "wait_timeout_seconds"]),
                condition=None
                if source == "none"
                else dict(
                    source=source,
                    operator=values[prefix + "condition_operator"],
                    value=values[prefix + "condition_value"],
                ),
            )
        )
        days[stage] = values[prefix + "weekdays"]
    return dict(rows=rows, run_timeout_seconds=int(values["run_timeout_seconds"])), days
