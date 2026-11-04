# P3a Backend A1 handoff (checkpoint)

A1 settings path is callable in isolated native Home Assistant. **Nutrient engine remains unsupported; this is not P3a delivery or hardware validation.** No control.py/Card/manifest/version changes, no commit/push/release.

## Frozen continuation API

- `Tank.write_settings(*, parameters=None, dosing_parameters=None, control=None, sources=None, expected_revision=None) -> int`: synchronous validation + one ConfigEntry update under caller-owned `Tank.lock`; reads latest options, increments persistent revision only for changed settings, publishes. Do not call without the lock. ConfigEntry scheduled persistence is not fsync.
- Number retains existing native entity ACL, identity/generation/live guards; then calls the writer with latest full parameter group.
- Native Options retains private opening revision for nutrient edits, authorizes before/after lock, submits explicit fields merged with latest control. Legacy source/P2 form preserves latest-merge semantics for compatibility with frozen P2 regression.
- Registered `apply_control_settings` exact payload per contract; admin/internal policy before target lookup and after Tank.lock, loaded/active/current runtime + registry recheck, CAS + one validated update. Optional native response `{applied: true, settings_revision: N}`.
- Commissioned nutrient configuration projects schema3 on the actual `:control_status` Sensor. Missing `control.supports_nutrient` is false; capability false, nutrient switch unavailable and no nutrient native map. No P2 start-flow semantics changed.
- `dosing_settings.py`: `DEFAULTS`, `RANGES`, `CONTROL_FIELDS`, `validate_dosing(parameters, dosing, control)` for A2 reuse. All 13 settings keys are independent of original 10 SPECS.

## Authentic evidence so far

`tools/evidence.py` retains exact source/test snapshots, hashes, command, child exit and raw log:
- `p3a-a1-01-native-red`: 1 failed, child 1 (native valid nutrient Save leaves dosing absent).
- `p3a-a1-02-native-green`: 7 passed, child 0 (1 new + 6 existing P2 Options).
- `p3a-a1-03-service-red`: 1 failed, child 1 (registered group mutation absent, parameters unchanged).
- `p3a-a1-04-service-green`: 2 passed, child 0.
- `p3a-a1-05-wire-red`: 1 failed, child 1 (actual native Sensor still schema2 after commissioning).
- `p3a-a1-06-wire-green`: 3 passed, child 0.
- `p3a-a1-07-regression`: original 151 passed, child 0; old tests unchanged. Five existing dependency deprecation warnings.

## Not connected (A2)

Controller `supports_nutrient`, nutrient actions/native map, necessary circulation lease, bounded pulse/feedback/cleanup, sample barriers/report/token validation, nutrient restart reconciliation and run hot-tightening. Current wire dose progress is truthful zero/no phase because no nutrient execution occurs. Full Issue #3 remains open.

Parent recovery checkpoint: A1 setting implementation and its shipped-UI/native service boundary are now exercised; still unreviewed and unpublished.

- Preserved the worker RED/GREEN and original 151-case regression; do not restart A1 from those old snapshots.
- Reopen-binding defect: p3a-a1-08 genuine RED (nutrient/circulation selectors returned no saved target); fixed by resolving all three binding roles.
- Native discovery metadata: p3a-a1-09/10 RED for missing apply_control_settings fields; services.yaml now exposes all five fields and a native config-entry selector. Initial queued-auth test lacked AuthManager (harness failure retained); after fixture initialization, real deletion after the settings-lock queue denies with unchanged options/runtime and zero outputs.
- p3a-a1-11 genuine Boolean-coercion RED for three new numeric Options fields; DosingSelector rejects bool before Core float conversion. No global SDK patch.
- Native translations in English/Traditional Chinese completed. Legacy exact-key metadata assertion extended with the explicit new keys, preserving every original key; raw failure retained in p3a-a1-13.
- p3a-a1-14-parent-final-green: complete 159 passed, five upstream warnings. p3a-a1-15-final-native-fields: eight focused passes after trimming YAML EOF whitespace. No overlapping totals added.
- Ruff check/format/compile and tracked diff check passed. New tools/p3a_settings_bridge.py also linted/formatted.
- p3a-settings-bridge-03-final: actual root Card JS -> native registered HA group handler -> ConfigEntry/Number readback; Apply, zero-call Cancel and real Number-induced CAS conflict pass, zero hardware calls, before/after source inventory identical. This is not an HA frontend host or physical test.
- Remaining exactly A2: nutrient/circulation execution, sample barriers, budgets/late-I/O/stop/restart/hot-tightening, then full integrated SPEC and quality. Controller remains P2 source2038ec1b and supports_nutrient false; no new source was staged/committed/pushed.

