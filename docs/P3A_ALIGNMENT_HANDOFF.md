# Goal alignment implementation checkpoint

2026-11-03. Local unreviewed P3a successor; not full P3, not publication/deployment approval.

## Goal reconciliation actually applied

Both repos now have updated README, DEVELOPMENT_PLAN, DEVELOPMENT_SPEC and identical GOAL_ALIGNMENT.md. Published P2 is separated from the locally connected/unapproved P3a candidate. Already-frozen engineering decisions are no longer all presented as waiting for user input. The original acid, independent mixing, configurable four-stage order/overlap/relative timing/conditions/weekdays/preview, recipe and downstream-quality scope is retained. No scheduler, stage_link or browser-owned stop timer was added. Eight current docs passed local-link and selected stale-claim checks; the three shared docs are byte-identical. Historical handoffs and immutable evidence were not rewritten.

## Concrete native implementation, not another framework

- `p3a-align-01` genuine RED6 -> `02` GREEN10 including overlap: initial sequence None/bool/negative, future/stale/malformed timestamp could previously admit an actual run. The selected measurement token must now be valid before admission/output and during domain validation; rejected initial frames produce zero output calls.
- `03` genuine native second-run RED -> `04` GREEN16 including overlap: relaxed settings remained blocked by the previous run's cached safety bounds. Only a newly requested run now refreshes settings before validation; current-run hot relaxation remains forbidden and the existing bounds cases remain green.
- `05` genuine RED -> `06` GREEN8: native start_flow executed65 complete zero-dose runs with real circulation and genuinely new same-value reports, proving65 unique run IDs. The nutrient request cache incorrectly kept65 receipts; it now evicts oldest beyond64, as the P2 policy already required. No preseeded fake history or SDK replacement was used.
- `07` genuine mixed-commissioning RED -> `08` GREEN46: native emergency previously closed only refill while commissioned nutrient/circulation stayed ON. `Controller.running` now aggregates separate P2 pending ownership and NutrientStage.owns_io, instead of one stage overwriting the other's stop truth. Emergency claims the explicitly commissioned emergency closure scope, and both owned cleanup routes run independently; identity loss remains unknown/fault rather than closure by a reused name.
- `09` supplemental GREEN10: both refill and nutrient OFF-ACK holds keep overall running true until each role actually settles; the other completed cleanup cannot hide the pending role. These were verification probes after the concrete mixed-emergency repair, not invented RED.

Production edits: control.py, nutrient.py. Native tests: new test_p3_dosing_initial.py and narrow additions to test_p3_dosing_lifecycle.py. Shared wire/parameter shape did not change; Card JS remains8cc5d7e3bbe1898f163b0057b703c1e348d0a623ae8c1511c20bfcff73ad3d9f.

## Final real results

- `docs/evidence/p3a-align-10-final-regression`: child0, **229 passed**,5 upstream deprecation warnings,91.61s. Parent authenticated all70 pre-run source/test fingerprints against current bytes. Do not sum focused counts.
- `p3a-dosing-bridge-03-aligned`: shipped JS -> native switches -> fake circulation/pump -> midpoint native OFF0.003335s -> required mix/new sample -> completed, page errors[], IRRfalse.
- `p3a-settings-bridge-05-aligned`: actual group Apply/Cancel/revision/conflict readback still passed with connected engine, all_hardware_calls[].
- Ruff/import/format and backend diff checks passed before execution. Exact per-run source bytes, commands, actual child exits and raw failures remain in new evidence directories.

## Next actual incomplete gate

The fixes above close the previously named initial-token, next-run refresh, cache-cap and mixed-emergency ownership defects. Do not reopen them just because an older handoff lists them.

Before P3a publication: resolve/review reachable cancellation/late-I/O and internal OFF causal-context cases, historical stage projection, current single-owner circulation record/stop ordering and selected in-flight sample boundaries. Current scope rejects sharing and standalone mix is unavailable: a general multi-owner workflow/lease framework is not a substitute milestone; add actual multi-owner arbitration with acid/independent mixing, not an unrelated architecture project. Independent SPEC then quality remains required, with the existing two concrete-repair-cycle budget. No independent verdict is claimed.

Next primary functionality after that bounded gate is **acid plus independent mixing**, then the full configurable four-stage execution and minimal editor/preview, not more evidence-only increments. These are still unimplemented and are not claimed by this checkpoint.

No stage/commit/push/tag/release, original HA access, credentials, physical-device actuation or deployment in this tranche.
