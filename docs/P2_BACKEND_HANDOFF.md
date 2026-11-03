# P2 Backend handoff — 0.2.0 candidate

## Implemented and exercised

Native Options commissioning of an explicit registry-bound refill Switch; master/refill/run Switches; emergency/reset Buttons; start_flow native service with explicit entry target and optional receipt; separate schema2 control Sensor while preserving the schema1 monitor and ten Number keys. Unsupported P3 stage Switches remain unavailable. No scheduler, raw-output UI, dosing or irrigation permission.

Controller owns source validity, actual-admission weekdays, low/high-level start/stop, conservative high/timeout bounds, one-run/busy behavior, bounded feedback, cancellation/unload/STOP cleanup, late ON/OFF settlement and persistent emergency/fault handling. Human starts require active admin; native internal automation contexts are allowed. Native output OFF uses internal safety authority and parent_id tracing of the initiating run/stop, so a removed user cannot prevent safe closure. Unknown closure remains visible rather than fabricated OFF.

## Verified results (separate evidence classes)

- Complete native Core suite after Q1: 151 passed, zero skips, 5 upstream deprecation warnings, docs/evidence/p2-q1-exact-index/native/ (exact consumed Git blobs). Do not add focused runs to this total.
- SPEC-1 context regression: p2-43-context-red was five assertion failures; p2-44-context-green was five passes. Normal flow/master/refill OFF, emergency and user removal during ON are covered.
- Starting-bound defect: original p2-38 and parent p2-39 RED preserved; parent p2-40 GREEN preserves tightened timeout during starting and rechecks before acceptance. Its adjacent high-water test was already green and is supplementary coverage.
- Local shipped Card -> real isolated native HA services -> native SwitchEntity fake hardware: tools/p2_bridge.py, docs/evidence/p2-q1-exact-index/bridge/. Ten browser UI actions, four hardware ON/OFF cycles, high water/normal stop/emergency-reset/external-service state sync. This is not a live HA frontend or physical-device test.
- Card canonical is separate: Node9, Chromium23, docs/evidence/p2-07-parent-canonical/ in the sibling repository.
- Parent fixed two import-order lint findings in tools/p2_bridge.py after the first combined command; subsequent ruff check/format and compile passed. Do not call that earlier command wholly successful.

## Legacy-test adaptation

P1 numbers/defaults/metadata/persistence/source boundaries remain asserted. ids() now intentionally selects only Numbers plus the original status instead of accidentally iterating P2 Buttons/Switches. Native inventory asserts both schema1 and schema2. Package-wide absence of control platforms was superseded by the authorized P2 feature; replacement asserts output dispatch is Controller-only and no duplicate MQTT client. Original P1 no-output fixture remains in place. Metadata expectations now match version0.2.0 and the actual added Options fields. Historical P1 snapshots remain unchanged.

## Local reviews complete; publication/CI separately verified

Initial independent SPEC review found one must-fix: human stop Context lost. Parent fixed it and executed the permanent tests plus the independently authored adjacent probe (only a ConfigEntry/runtime_data harness typo and owned temp path were corrected in a preserved copy). That probe passed denial, deleted-user high-water OFF, causal parent and no stale-context reuse. Execution of another author's probe does not constitute that reviewer's final approval.

Independent SPEC repair recheck subsequently completed with source-bound PASS: docs/reviews/p2-spec-recheck-final.md and docs/evidence/p2-spec-recheck-independent/. The initial blocker/history is preserved. The initial quality review found Q1 (starting source loss could be forgotten); its seven-line repair has genuine RED/GREEN and a source-bound SPEC PASS at docs/reviews/p2-q1-spec-recheck.md. Q1 source-bound SPEC PASS and final quality APPROVED are preserved at docs/reviews/p2-q1-spec-recheck.md and p2-q1-quality-recheck.md; the original unchanged review scope is explicitly composed. Green tests alone were not used as approval. Original initial review and probe bytes are preserved under docs/reviews/p2-recovery/.

No tag/release/deployment or original HA access. Source publication and exact-head CI are verified separately against remote commits. Shared specs/readmes now distinguish the P2 local candidate from P3–P5 planned work. See P2_ACCEPTANCE.md for exact remaining gates.

## Next step

SPEC-1 independent recheck is PASS. Q1 SPEC and quality rechecks are complete. Do not reopen resolved blockers, restart discovery or reimplement existing passing work. Freeze staged source/test/JS bytes after concrete fixes, run final gates on that candidate, update tracking and publish only after approval; bind hosted CI to both exact commit heads. Physical deployment and HACS acceptance remain separately authorized.
