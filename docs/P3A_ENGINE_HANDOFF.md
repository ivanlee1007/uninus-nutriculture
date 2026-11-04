# P3a A2 resume — first genuine native dosing RED captured

> Continue the approved P3A-v1 contract; do not restart A1/P2 or reduce full Issue#3 scope. This is an implementation handoff, not another delivery milestone. No live HA/credentials/deployment/release. Source publication only after integrated SPEC then quality.

## Current owned state

- Backend main baseline bc3915af2bd42870620d11c396bd53e62f072324; Card main baseline c3d4fd8fbde34823ed0cbe581b1e3007f76f0e2c. Both have uncommitted P3 settings/UI changes. Preserve all dirty/untracked files and immutable RED/GREEN.
- A1 settings implementation is exercised: docs/P3A_BACKEND_A1_HANDOFF.md, docs/P3A_LOCAL_CHECKPOINT.json. Original 151 regressions plus settings/metadata/type/revocation cases: 159 passes in p3a-a1-14; final 8 focused cases in p3a-a1-15. Do not add overlapping counts.
- Card schema3 group editor/fixtures/offline demo: Node10, Chromium30, p3a-card-09-demo-green. Root JS8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f. Actual settings bridge p3a-settings-bridge-03-final uses shipped JS/native Core and zero outputs; NOT evidence of a dosing engine.
- Controller remains P2 source2038ec1b. A1 supports_nutrient is absent/false by design. Do not advertise support without the complete native action path.

## Immediate behavior-first cursor

New permanent tests/test_p3_dosing.py has its own dosing_hass fixture, actual native SwitchEntity outputs and unmodified ServiceRegistry. It does NOT reuse A1's nutrient_hass fixture, whose teardown intentionally prohibits all output calls.

Executed tools/evidence.py p3a-a2-01-native-nutrient-red tests/test_p3_dosing.py -q: child exit1, genuine native action failure at automation_enabled ON, ServiceValidationError(uncommissioned). The Options transaction succeeded, nutrient_commissioned=True, no refill binding intentionally configured. Not an import/setup/scaffolding failure: P2 admission incorrectly requires refill commissioning for a nutrient-only tank.

The full test continues through native nutrient Enable without actuation -> start_flow -> circulation before nutrient -> EC reaches midpoint0.85 during2s pulse -> pump OFF within0.75s, circulation retained -> post-mix/new EC0.86 -> stable completion. It asserts no irrigation permission. Fake nutrient device has its own3s cutoff; test requires native OFF before that and excludes the cutoff event as success. Durations and limit metadata are valid, actor declarations are fixture-only.

Use this real RED first. Do not fake GREEN with support flags or weaken assertions. Once this native vertical path is green, add one failing safety/edge behavior at a time. An existing expectation of nutrient capability false in test_p3_wire.py must be evolved narrowly only when the engine genuinely works; retain its historical A1 snapshot and all real binding/state assertions.

## Production ownership and P2 compatibility

- A2 owns control.py, switch.py, sensor.py, __init__.py and small connected nutrient helper(s) if needed. Parent owns common contract, original bridge and new dosing bridge. Other A1 settings files may change only for a concrete necessary interface, not a rewrite.
- Keep physical service dispatch in control.py via a controller-owned adapter; existing tests/test_safety.py enforces that owner and no duplicate MQTT client. A helper engine may ask Controller to dispatch, not call arbitrary HA services itself.
- Uncommissioned/P2-only entries must still export schema2, no nutrient capability/map, and preserve original151 behavior. supports_nutrient must be per-entry configured capability, not a global true flag leaking nutrient support into schema2.
- For a nutrient-only entry, master admission, startup/restart, emergency/reset and output truth cannot depend on refill binding. Inspect every P2-only binding assumption, not just the first failure line.
- Persist nutrient_enabled, expose native availability/map only when genuinely supported. Runtime start chooses one supported enabled stage; refill+nutrient composition is explicitly rejected in this slice, not silently serialized. Enable only permits; never actuates. Switch repeated ON is idempotent for current run; new different start_flow request while busy refuses. Preserve request_id bounds and tracing.
- During nutrient execution, stage_states.refill cannot equal dosing/mixing/etc (these are not valid refill stage states). Project skipped_disabled/idle as appropriate and nutrient running/phase; actual flow_state equals Sensor state. P2-only projection stays unchanged.

## Required asynchronous safety

- Plan/weekday admission after awaited resources, before the stage's first physical ON. Already-started stage crossing midnight does not suddenly stop; no deferred weekday scheduler or manual bypass.
- Recheck authority, entry generation, source/binding and gates after awaits and before each new physical opening. Internally authorized OFF uses parent Context trace, so a deleted/revoked human cannot prevent closure.
- Pump pulse deadline starts at send, not provider ACK. EC>=midpoint stops even with pending ON; invalid/minimum-level/dangerous source must latch/revoke even if it recovers before ACK. Do not repeat the fixed P2 starting-event omission.
- Track pump AND circulation pending ON/OFF, bounded confirmation, late ON follow-up OFF and truthful running/stopping/fault. No restart while old operations may energize later. Do not hold an admission lock that prevents a deadline-triggered OFF until ON returns.
- Confirm circulation ON before pump. Pump OFF confirmation before post-mix; no further dose without an effective new sample after the post-mix barrier. Minimum mixing survives independent mix_enabled OFF. Release circulation only after all legal owned leases end; current slice rejects cross-entry sharing.
- Track reserved/elapsed ON conservatively, max pulses, stage ec_timeout minutes converted at boundary, whole flow deadline and cleanup deadline separately. Tightening applies immediately and relaxation never extends the admitted budget.
- Stop/master OFF/current-stage OFF/acute fault first revoke future ON and then settle owned outputs. Enabling another stage is not permission to alter an admitted plan or silently chain it. No automatic resume on enable/reset/restart.
- High-pH threshold6.8/600s is an alarm reason, not a hidden global emergency stop. Low pH3.8/high EC1.3 remain independent danger defaults; configurable settings are already present. ready_for_irrigation remainsfalse.

## Verified SDK traps (installed Core2026.10.4 primary source)

- core.py:2477–2494 emits EVENT_STATE_REPORTED ONLY when both value and attributes are unchanged. Changed value/attributes use EVENT_STATE_CHANGED. Listen to both relevant scoped events to observe changed and same-value measurements; do not double-count or assume all writes emit reported.
- core.py:1703–1744 public bus.async_listen(event, callback, event_filter=...) requires a @callback filter for EVENT_STATE_REPORTED. Explicit run_immediately=True/False now reports custom-integration ERROR. Do not use that old example or private SDK listener methods. Capture event state/token in callbacks rather than later rereading a recovered State to erase invalidation.
- ConfigEntry.async_create_background_task(hass, coro, name, eager_start=False) is available, tied to entry lifecycle and excluded from async_block_till_done. Inspect its cancellation ordering before using it for long runs. Do not leave a whole many-minute dosing loop as a normal task that hangs native fixture drains; do not patch Core task sets. Safety cleanup must survive cancellation under the explicit owning stop/unload path.
- Reported mode requires the operator declaration already in settings. Attribute-only changes cannot be treated as new physical samples; sequence/timestamp need explicit selected fields, monotonic/new-barrier rules, finite scalar types and no future timestamps. No token/new sample means wait then timeout, never redose based on the last cached reading.

## Verification and handoff

Use existing .venv/Scripts/python.exe, pytest and tools/evidence.py with NEW p3a-a2-* labels/basetemps. Never overwrite prior receipts. Preserve first RED source and tests (already captured). Run original P1/P2/settings regression after wiring; no mass assertion changes. Keep TDD one real behavior at a time, early progress after first handler and first native pulse. Final engine -> real shipped Card bridge plus integrated SPEC->quality precede commit/push. Full acid/mix/flexible graph scope remains open after P3a.
