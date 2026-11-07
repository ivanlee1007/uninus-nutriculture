"""Separate versioned P1 monitoring and P2 control status contracts."""

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            TankStatus(entry.runtime_data),
            ControlStatus(entry.runtime_data),
            QualityStatus(entry.runtime_data),
            ResultStatus(entry.runtime_data),
        ]
    )


class TankStatus(SensorEntity):
    _attr_should_poll = False

    def __init__(self, tank):
        self.tank = tank
        self._attr_unique_id = f"{tank.entry.entry_id}:status"
        self._attr_name = f"{tank.entry.title} status"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.tank.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.tank.listeners.discard(self.async_write_ha_state))
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, list(self.tank.sources.values()), self._source_changed
            )
        )
        self.async_on_remove(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._number_changed)
        )
        self.async_on_remove(self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._number_changed))
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._source_changed, timedelta(seconds=5), cancel_on_shutdown=True
            )
        )

    @callback
    def _number_changed(self, event):
        if event.data.get("entity_id", "").startswith("number."):
            self.async_write_ha_state()

    @callback
    def _source_changed(self, event):
        self.async_write_ha_state()

    @property
    def native_value(self):
        return self.tank.snapshot()[0]

    @property
    def extra_state_attributes(self):
        return self.tank.snapshot()[1]


class QualityStatus(TankStatus):
    def __init__(self, tank):
        super().__init__(tank)
        self._attr_unique_id = f"{tank.entry.entry_id}:quality_status"
        self._attr_name = f"{tank.entry.title} 品質狀態"

    @property
    def native_value(self):
        try:
            return self.tank.quality.dto()["quality"]["state"]
        except Exception:
            return "invalid"

    @property
    def extra_state_attributes(self):
        try:
            return self.tank.quality.dto()
        except Exception:
            return {}


class ControlStatus(TankStatus):
    def __init__(self, tank):
        super().__init__(tank)
        self._attr_unique_id = f"{tank.entry.entry_id}:control_status"
        self._attr_name = f"{tank.entry.title} control status"

    @callback
    def _number_changed(self, event):
        super()._number_changed(event)
        entity_id = event.data.get("entity_id", "")
        config = self.tank.entry.options.get("control", {})
        if not entity_id.startswith("switch.") or not (
            config.get("nutrient_commissioned")
            or config.get("acid_commissioned")
            or config.get("mix_commissioned")
        ):
            return
        from homeassistant.exceptions import ServiceValidationError

        from .control_settings import resolve

        for role in ("nutrient", "acid", "circulation"):
            try:
                target = resolve(self.hass, config.get(role + "_binding"))
            except ServiceValidationError:
                continue
            if entity_id == target:
                self.async_write_ha_state()
                return

    @property
    def native_value(self):
        return self.tank.control.flow_state

    @property
    def extra_state_attributes(self):
        from .const import DOMAIN
        from .control_settings import DAYS, STAGES

        control = self.tank.control
        base = self.tank.snapshot()[1]
        config = self.tank.entry.options.get("control", {})
        registry = er.async_get(self.hass)
        targets = {}
        for key, domain in (
            ("automation_enabled", "switch"),
            ("refill_enabled", "switch"),
            ("nutrient_enabled", "switch"),
            ("acid_enabled", "switch"),
            ("mix_enabled", "switch"),
            ("flow_run", "switch"),
            ("emergency_stop", "button"),
            ("reset_fault", "button"),
        ):
            if (
                key == "refill_enabled"
                and self.tank.entry.options.get("control_contract_version") == 4
                and not config.get("commissioned")
            ):
                continue
            if key == "mix_enabled" and not control.supports_mix:
                continue
            if key == "acid_enabled" and not control.supports_acid:
                continue
            if key == "nutrient_enabled" and not control.supports_nutrient:
                continue
            entity_id = registry.async_get_entity_id(
                domain, DOMAIN, f"{self.tank.entry.entry_id}:{key}"
            )
            row = registry.async_get(entity_id) if entity_id else None
            if (
                row
                and not row.disabled_by
                and row.config_entry_id == self.tank.entry.entry_id
                and self.hass.states.get(entity_id) is not None
                and self.tank.active
            ):
                targets[key] = entity_id
        nutrient_supported = bool(getattr(control, "supports_nutrient", False))
        extra = {}
        if config.get("nutrient_commissioned"):
            from homeassistant.exceptions import ServiceValidationError

            from .control_settings import resolve

            outputs = {}
            for stage in ("nutrient", "circulation"):
                try:
                    entity_id = resolve(self.hass, config.get(stage + "_binding"))
                    state = self.hass.states.get(entity_id)
                    outputs[stage] = (
                        state.state if state and state.state in ("on", "off") else "unknown"
                    )
                except ServiceValidationError:
                    outputs[stage] = "unknown"
            extra = {
                "schema_version": 3,
                "reasons": [
                    *base.get("reasons", []),
                    *(["ph_high_alarm"] if control.ph_high_alarm_active else []),
                ],
                "settings_target": {
                    "config_entry_id": self.tank.entry.entry_id,
                    "service": "apply_control_settings",
                },
                "settings_revision": self.tank.entry.options.get("settings_revision", 0),
                "dosing_parameters": dict(self.tank.entry.options.get("dosing_parameters", {})),
                "nutrient_phase": getattr(control, "nutrient_phase", None),
                "dose_progress": dict(
                    getattr(
                        control,
                        "dose_progress",
                        {"pulse_count": 0, "reserved_on_seconds": 0, "stable_count": 0},
                    )
                ),
                "output_states": outputs,
            }
        if self.tank.entry.options.get("control_contract_version") == 5:
            from .p3c_projection import snapshot_v5

            return snapshot_v5(self.tank, base, targets)
        if self.tank.entry.options.get("control_contract_version") == 4:
            from .p3b_projection import snapshot_v4

            return snapshot_v4(self.tank, base, targets)
        return {
            **base,
            "schema_version": 2,
            "mode": "control",
            "capabilities": {
                stage: stage == "refill" or (stage == "nutrient" and nutrient_supported)
                for stage in STAGES
            },
            "control_entities": targets,
            "allowed_weekdays": config.get(
                "allowed_weekdays", {stage: list(DAYS) for stage in STAGES}
            ),
            "stage_states": {
                "refill": "skipped_disabled"
                if nutrient_supported
                and (
                    control.run_stage == "nutrient"
                    or (control.run_stage is None and control.nutrient)
                )
                else control.flow_state,
                "nutrient": (
                    (
                        control.nutrient_stage.result
                        if not control.nutrient_stage.owns_io
                        and control.nutrient_stage.result is not None
                        else "running"
                        if control.flow_state
                        in ("dosing", "mixing", "waiting_sample", "stabilizing")
                        else control.flow_state
                    )
                    if control.run_stage == "nutrient"
                    else "skipped_disabled"
                    if control.run_stage == "refill"
                    else "idle"
                )
                if nutrient_supported
                else "unsupported",
                "acid": "unsupported",
                "mix": "unsupported",
            },
            "flow_state": control.flow_state,
            "fault": control.fault,
            "run_id": control.run_id,
            **extra,
        }


class ResultStatus(SensorEntity):
    _attr_should_poll = False

    def __init__(self, tank):
        self.tank = tank
        self._attr_unique_id = f"{tank.entry.entry_id}:result_status"
        self._attr_name = f"{tank.entry.title} 結果狀態"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.tank.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.tank.listeners.discard(self.async_write_ha_state))

    @property
    def native_value(self):
        dto = self.tank.results.dto()
        if dto["support"] == "unsupported":
            return "unsupported"
        run = dto["current_run"] or dto["last_result"]
        return run["state"] if run else "idle"

    @property
    def extra_state_attributes(self):
        return self.tank.results.dto()
