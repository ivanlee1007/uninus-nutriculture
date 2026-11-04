# P3a B2 recovery + bounded B3 safety checkpoint

2026-11-03. **Local unreviewed execution candidate; safety acceptance remains incomplete. No P3 commit/push/tag/release/live deployment.** This replaces the stale 'B2 in progress, green pending' cursor, not any immutable run.

## What survived the provider interruption

The B2 worker stopped with HTTP429 after41 API calls. Its scratch checkpoint and source/tests survived. Parent resumed those exact dirty files rather than restarting the implementation. The provider message named22:10 as the then-expected reset; no successful replacement worker or independent review is inferred from that message.

B2 source implemented conservative send-to-confirmed-OFF accounting with reservation floor and unresolved-ON interval retention, ec_timeout minutes converted to an owned stage deadline checked through ACK waits, admitted monotone hot bounds, committed required-mix extension, and an inner fresh-sample stability loop. The selected native cases cover actual elapsed/reservation exhaustion, both-role held ACK stage timeout, pulse/safe-level/midpoint changes through the native group writer, unknown-ON budget, required mixing, stable interval and old-token sample binding.

- New `p3a-a2c-12-recovered-focused`: actual child0 /11 passed; includes the previously unverified old-token burst repair.
- After import/format cleanup, `p3a-a2c-13-recovered-regression`: actual child0 /208 passed. This is historical; final candidate below supersedes it.

## Additional parent behavior RED→GREEN

1. `a2c-14-invalid-callback-red`: native invalid→recovered EC caused an uncaught ValueError in Core's event callback even though safety revocation stopped the pump. Guarding token/value consumption after latched revocation fixes the callback without clearing the fault. `a2c-15`:3 passed.
2. `a2c-16-above-target-burst-red`: a genuinely new EC1.0 sample (above target but outside stable window) followed by stale-token EC0.70 could wrongly open another dose. An above-target sample now stays in fresh-sample wait; only a genuinely consumed below-midpoint sample can leave that loop for another dose. `a2c-17`:4 passed. The original0.86 accepted-sample assertion is retained.
3. `a2d-01-idle-emergency-red` -> `02`: explicit native emergency on a nutrient-only entry now closes both commissioned roles even if another caller energized them while no owned run was active. Output truth is read back, fake3s cutoff is not closure evidence. **This repair is deliberately N-only; mixed refill+nutrient commissioning emergency aggregation is still a named gap.**
4. `a2d-03-reset-danger-red` -> `04`: reset refuses numerically valid but unsafe minimum level, dangerous low pH or dangerous high EC; it retains the emergency fault/masterOFF. Reset uses current validated configuration, not a stale admitted-run bounds object.
5. `a2d-05-native-lifecycle-probe`: real ConfigEntries async_unload and real HA async_start/async_stop close both roles and deactivate the controller. These two cases were already green with existing cleanup; supplemental verification, NOT new RED or process-crash proof.
6. `a2d-06-high-ph-alarm-red` -> `08-high-ph-native-green`: configurable continuous high-pH delay now adds native schema3 `reasons: ph_high_alarm`, without making it an emergency or aborting necessary circulation. Equality at threshold clears it. Source event payloads, freshness/units and the owned monotonic observer clock are used; unconfigured P2 schema is unchanged. `07` was an incomplete GREEN attempt: alarm assertions passed, but the test assumed accepted background start meant physical circulation had already started. The corrected test waits on the fake native output's actual entered_on Event; production was not weakened.
7. `a2d-09-nutrient-idle-red` actually passed. Its name is historical only: the native idle projection probe is supplemental verification, not behavioral RED; no __init__.py change was made for that hypothesis.

## Frozen final local validation

- `docs/evidence/p3a-a2d-10-recovery-final-regression`: actual child0, **218 passed**,5 upstream deprecation warnings,82.70s. Focused runs overlap; do not add counts.
- Ruff check for all production Python and dosing test files passed; owned code formatted before final execution.
- `docs/evidence/p3a-dosing-bridge-02-recovered`: real shipped Card SHA8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f -> native master/nutrient/run Switch calls -> fake circulation/N ON -> midpoint OFF -> mix -> new sample -> completed; native OFF reaction0.001534s, page errors[], IRRfalse. Five fake hardware calls include a conservative repeated N OFF. No live HA or physical device access. Source-manifest before/after equality is required by the runner.
- Exact final production/test bytes and command/source SHA are in final regression run.json + pre-run snapshot; bridge consumed-input hashes are in its source-manifest.json. Parent readback authenticated all69 native receipt fingerprints. No later production/native-test edits in this checkpoint.
- `docs/evidence/p3a-settings-bridge-04-engine-connected` reruns the real shipped group editor against the connected engine: Apply/Cancel/conflict/revision readback passed, **zero hardware calls**. Only the parent bridge's historical A1 unsupported-capability assertion was changed to true and its receipt now reads actual capability; no side-effect assertions were weakened. Its own before/after source manifest matches, and Ruff/format/diff checks passed.

## Remaining bounded work — do not approve the entire P3a slice

- Initial malformed/missing/old/future sample-token admission and remaining selected token boundary cases; next-run parameter relaxation and complete bound-direction coverage need explicit checks. Existing max-budget/hot tests are selected real cases, not every arbitrary Cartesian permutation.
- Mixed refill+nutrient commissioning emergency must aggregate all configured/pending roles truthfully without handing P2 late I/O into nutrient-only cleanup. Do not broaden the N-only repair by merely setting one shared running flag.
- Remaining reachable auth-await/duplicate-stop/repeated cancellation/late-OFF boundaries, internal OFF context with deleted user, replay dictionary nutrient64-entry cap, historical stage ownership projection, explicit owned lease accounting.
- Timed high-pH native reason is now implemented/tested, but long-duration/stale/recovery/restart/parameter-change edges and any outbound notification transport are not claimed. It remains observational, not an acute stop.
- Final integrated acceptance on the successor, independent SPEC then independent quality/security, exact Git input freeze and exact-head hosted CI remain open. Current source is not approved for deployment. Full Issue#3 acid, independent mixing and arbitrary editable flow remain future primary functionality, not removed scope.
