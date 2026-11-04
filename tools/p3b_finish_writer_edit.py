"""One-time historical edit, not an installable product helper."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'custom_components/uninus_nutriculture/manager.py'
s=p.read_text();s=s.replace('class Tank:', '_UNSET = object()\n\n\nclass Tank:')
for key in ('parameters','dosing_parameters','acid_parameters','mix_parameters','safety_parameters','control','sources'):
 s=s.replace(f'        {key}=None,',f'        {key}=_UNSET,')
needle='        candidate = dict(options)'
s=s.replace(needle,'''        # Null is a protocol value, never an alias for omitted arguments.
        for name, value in (("parameters", parameters), ("control", control),
                            ("sources", sources), ("safety_parameters", safety_parameters)):
            if value is None:
                raise ServiceValidationError("invalid_parameters")
        config_input = control if control is not _UNSET else options.get("control", {})
        for name, value, role in (("dosing", dosing_parameters, "nutrient"),
                                  ("acid", acid_parameters, "acid"),
                                  ("mix", mix_parameters, "mix")):
            if value is None and config_input.get(role + "_commissioned"):
                raise ServiceValidationError("invalid_commissioning")
        candidate = dict(options)''')
s=s.replace('parameters if parameters is not None else', 'parameters if parameters is not _UNSET else')
s=s.replace('control if control is not None else', 'control if control is not _UNSET else')
s=s.replace('dosing_parameters if dosing_parameters is not None else', 'dosing_parameters if dosing_parameters is not _UNSET and dosing_parameters is not None else')
s=s.replace('(acid_parameters is None and mix_parameters is None', '(acid_parameters is _UNSET and mix_parameters is _UNSET')
s=s.replace('if acid_parameters is not None or mix_parameters is not None or', 'if acid_parameters is not _UNSET or mix_parameters is not _UNSET or')
s=s.replace('validate_v4(params, candidate, config, acid_parameters, mix_parameters, safety_parameters)', 'validate_v4(params, candidate, config,\n                        None if acid_parameters is _UNSET else acid_parameters,\n                        None if mix_parameters is _UNSET else mix_parameters,\n                        None if safety_parameters is _UNSET else safety_parameters)')
s=s.replace('if parameters is not None or', 'if parameters is not _UNSET or').replace('if control is not None:', 'if control is not _UNSET:').replace('if sources:', 'if sources is not _UNSET:')
p.write_text(s)
p=root/'custom_components/uninus_nutriculture/config_flow.py';s=p.read_text();s=s.replace('                        tank.write_settings(\n                            control=config,','                        from .manager import _UNSET\n                        tank.write_settings(\n                            control=config,')
s=s.replace('else None,\n                            mix_parameters=', 'else _UNSET,\n                            mix_parameters=').replace('else None,\n                            safety_parameters=', 'else _UNSET,\n                            safety_parameters=').replace('else None,\n                            dosing_parameters=', 'else _UNSET,\n                            dosing_parameters=')
p.write_text(s)
p=root/'tests/test_boundaries.py';s=p.read_text();s=s.replace('            "ph_high_alarm_seconds",\n        }', '''            "ph_high_alarm_seconds",
            # P3b extends the exact set; no legacy key is removed.
            "acid_output", "acid_commissioned", "acid_device_max_on_seconds",
            "acid_protection_confirmed", "acid_alias_notes", "acid_sample_mode",
            "acid_sample_attribute", "acid_report_contract_confirmed", "mix_commissioned",
            "circulation_device_max_on_seconds", "circulation_protection_confirmed",
            "circulation_alias_notes", "acid_safe_min_level_m", "acid_pulse_seconds",
            "acid_max_total_on_seconds", "acid_max_pulses", "acid_post_mix_seconds",
            "acid_sample_wait_timeout_seconds", "acid_stable_samples",
            "acid_stable_interval_seconds", "acid_flow_timeout_seconds",
            "mix_safe_min_level_m", "mix_flow_timeout_seconds",
        }''');p.write_text(s)
