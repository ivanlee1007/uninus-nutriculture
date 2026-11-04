# P3a finite-finish candidate handoff

2026-11-03. **Local candidate for independent SPEC, not independent approval or deployment.** This supersedes old open cursors about the concrete finish defects below; full acid/mix/editable-flow scope remains pending.

## Newly completed native behaviors

- `p3a-finish-01` genuine failure: immediate native flow_run OFF after accepted start exposed CancelledError because the background run was cancelled before its body/finally entered. `02` passes: stop explicitly owns bounded shielded cleanup for that pre-entry cancellation, without losing pending I/O or denying caller cancellation after cleanup.
- `03` genuine failure -> `04`: turning nutrient Enabled OFF while active no longer overwrites aborted with idle. Controller records accepted `run_stage`; schema3 stage projection uses actual accepted owner rather than current Enabled flags, so skipped refill is not relabeled dosing/aborted and subsequent refill is not mislabeled nutrient.
- `05`: genuine native AuthManager removal during held pump ON ACK cannot block midpoint OFF. Recorded actual SwitchEntity Context has user_idNone and parent_id of original human run; no subsequent pump ON. This was already-green supplementary proof, not manufactured RED. Fixture adds a separate contexts list; existing outputs/calls/rows API unchanged.
- `06`: timestamp invalid-then-restored is genuine failure; initial sequence True-vs1 premise was not observable because Core compares those attributes equal. `07` partial GREEN attempt still failed that fixture premise. Corrected valid sequence baseline2 in `08` ensures the SDK really emits invalid bool frame, no SDK patch. Source callback now latches invalid selected token even when current state recovers. The historical labels/failed receipts remain.
- `09` genuine failure: rejected initial sample admission created phantom run_id. Only accepted nutrient admission now creates its run identity; no output/settings write occurs on rejected sample.
- `11` genuine failure: normal stop switched circulation OFF before nutrient OFF ACK confirmed. Normal completion/cancellation now retains circulation until bounded nutrient confirmation; acute fault/revocation still triggers prompt independent best-effort closure. Both role failures/late-ON paths remain tracked.
- `12` two genuine failures -> `13`: low-level event then restoration, or safe-min tightening during blocked normal-stop ACK, must escalate circulation closure and latch fault/masterOFF. Extracted source-only validation preserves the independent cleanup deadline rather than aborting cleanup at the run deadline.
- First `14` full237 was green, but dosing bridge05 failed; diagnostic rerun06 also failed. **Not classified as a harmless harness error.** Actual hardware ON/OFF occurred while control_status.output_states remained cached OFF until a later periodic refresh. `15` permanent native behavior RED reproduced actual pumpON/statusOFF. ControlStatus now listens to its already-bound outputs' native events through its own inherited listener; no browser optimistic state or pumping logic moved to sensor/Card. `16` focused9 and dosing bridge07 pass. Both original failed bridges and diagnostic JSON remain intact.

## Exact final results

- `docs/evidence/p3a-finish-17-review-candidate`: actual child0, **238 passed**,5 upstream deprecation warnings,93.91s. Earlier234/237 and focused counts are historical/overlapping, not totals to add.
- `p3a-dosing-bridge-08-final-source`: shipped Card SHA8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f -> three actual native switches -> circulation/pumpON -> midpoint OFF0.001195s -> required mix/new sample/completed; page_errors[], ready_for_irrigationfalse. Fake hardware only; no live HA.
- `p3a-settings-bridge-08-final-source`: same shipped JS group Apply/Cancel/revision/conflict path passes, hardware_calls[].
- Ruff/format passed before final execution. Native pre-run snapshots and source hashes live with each receipt; bridges record consumed-input before/after equality. Parent bridge now also retains actual native diagnostic snapshot/calls on browser failure; this does not fabricate success.

## Candidate scope / independent review

Authoritative P3A_NUTRIENT_CONTRACT.md §8 wins detailed P3a conflicts; DEVELOPMENT_SPEC and GOAL_ALIGNMENT retain full product goals. Only commissioned nutrient-only flow plus preserved P2 refill is implemented here; unsupported multi-stage combinations, acid and standalone mix remain rejected. No scheduler/stage_link; per-stage actual-admission weekdays; no irrigation permit. Native settings/CAS and shipped UI are jointly in scope.

Current single-entry NutrientStage record binds role identities, generation, Context and pending operations and retains sole circulation ownership through its required mix/stability. Cross-entry sharing is rejected and independent mix is unavailable, so there is no other legal owner in this slice. Judge that actual invariant, not a requirement to build an unused general workflow framework. Future acid/standalone mixing must extend the same ownership model rather than creating competing timers.

The independent reviewer must still assess all frozen clauses, nearby adversarial paths and the actual source boundaries; this handoff does not self-certify the engine. Normal vs acute-stop policy, repeated cancellation and stage ownership must be checked against captured failures. Bounded review/repair budget remains two concrete cycles. Do not close full Issue#3 or publish while SPEC/quality is absent.

Next primary implementation is acid plus independent mixing and then full configurable four-stage execution/editor/preview. No new version/tag/release/commit/push or original-HA access is authorized by this handoff; parent publication gate remains separate.
