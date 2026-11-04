# P3a review candidate — acceptance map

2026-11-03. **Candidate only; independent SPEC/quality verdicts pending.** Source publication, exact-head hosted CI, deployment and physical acceptance are separate. Full P3 is not completed.

## Frozen useful slice

Original P1 monitoring and P2 refill retained. Native Options and CAS group settings + shipped schema3 Card + native nutrient-only start/stop -> required circulation -> bounded pulse -> midpoint OFF -> minimum mix -> fresh sample/stability -> completion. Acid, standalone mix, editable multi-stage graph and irrigation permission are not supported in this slice and remain primary future work. Refuse unsupported combinations, not fixed implicit chaining. No schedule/stage_link.

P3A_NUTRIENT_CONTRACT.md §8 is the exact interface supplement; its stage/control/safety clauses remain in force. The actual-source single-owner record retains bound roles/generation/Context/pending operations through mix. No cross-entry sharing or other legal circulation owner exists yet. Future standalone mixing extends that owner model; an unrelated generic framework is not a release prerequisite.

## Acceptance-to-executed-check map

| Contract boundary | Named executed native/browser check |
|---|---|
| Native settings Save/Cancel/reopen and selector types | test_p3_options.py::test_native_save_cancel_reopen; test_native_numeric_selector_does_not_erase_boolean |
| Atomic settings/revision/CAS and queued authority | test_p3_settings.py::test_registered_atomic_apply_cas_and_number_revision; test_p3_recovery.py::test_removed_admin_queued_at_settings_lock_cannot_commit |
| Real schema/native map + P1/P2 compatibility | test_p3_wire.py plus all original P1/P2 cases in the final full run |
| Actual no-refill nutrient user path and midpoint | test_p3_dosing.py::test_native_nutrient_only_midpoint_stops_pump_before_pulse_then_mixes; shipped dosing bridge08 |
| Send-time deadline / pending ON revocation | test_pulse_deadline_starts_at_send_not_ack; test_pending_on_invalid_event_latches_even_after_recovery; test_pending_on_safety_event_latches_after_recovery |
| Per-ON identity/authority and actual weekday admission | test_p3_dosing_admission.py::test_circulation_ack_does_not_authorize_later_pump; test_weekday_only_at_final_stage_first_opening; test_registry_rename_resolved_before_pump_opening |
| Late-I/O, independent failures and foreign name reuse | test_p3_dosing_io.py::test_late_on_during_other_role_off_ack_cannot_report_stopped; test_failed_nutrient_off_still_closes_circulation; test_removed_identity_never_sends_off_to_reused_foreign_name |
| Runtime budget, stage/whole deadlines and hot bounds | test_p3_dosing_bounds.py named send-to-OFF, ec-minutes held-ACK, monotone writer, overbudget and committed-mix checks |
| Fresh samples / interval / initial token | test_p3_dosing_samples.py stable-cached-low/old-token burst checks; test_p3_dosing_initial.py initial invalid token and consecutive next-run settings checks |
| Basic native lifecycle/reset/emergency and mixed owners | test_p3_dosing_lifecycle.py real STOP/unload, reset danger, mixed three-role emergency and held-OFF owner-union checks |
| Final cancellation, truthful stage/trace, token invalidation, stop ordering and event projection | all named tests/test_p3_dosing_finish.py cases, including native immediate OFF, stage disable aborted, deleted principal OFF Context, invalid token recovery, normal vs acute stop and actual output events |
| Bounded replay | test_p3_dosing_initial.py::test_native_nutrient_request_receipts_evict_after_64_actual_runs (65 actual native completed zero-dose runs) |
| High-pH observational delay | test_p3_dosing_alarm.py::test_high_ph_delay_reason_is_native_visible_and_does_not_abort; not a notification delivery or emergency guarantee |
| Shipped group UI / no actuator effects | p3a-settings-bridge-08-final-source: Apply/Cancel/conflict/readback, hardware_calls[] |
| Shipped native controls / no optimistic output | p3a-dosing-bridge-08-final-source: actual native Switch calls and real fixture states/events |

## Current execution evidence

- `docs/evidence/p3a-finish-17-review-candidate`: actual child0, **238 passed**,5 upstream deprecation warnings,93.91s. No sum with focused runs.
- Shipped Card remains SHA8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f. Browser Chromium156.0.8078.4. Final dosing bridge native midpoint OFF0.001195s, page errors[], IRRfalse. Settings bridge zero outputs. All isolated fake hardware; no external HA or credentials.
- Important preserved failures: cancelled-before-body01, aborted projection03, token06/07 with documented sequence fixture correction08, phantom run09, normal-stop order11, stop-time unsafe escalation12, cached output projection15 and failed dosing bridges05/06. Read P3A_FINISH_HANDOFF.md; do not treat a misleading filename ending 'green' as a passed receipt.
- Current source/test pre-run snapshots are retained with run.json; bridges record full before/after consumed-input equality. Reviewer must add source-bound nearby counterexamples, not accept this map as a verdict.

Review/repair budget is two concrete cycles for this delivery slice. No P3 commits/push/tags/releases or physical deployment. After this bounded gate, acid/standalone mix and then full configurable flow are the next primary capabilities, not another evidence-only milestone.
