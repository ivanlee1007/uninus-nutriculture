# P3c backend R2 recovery

Scope: continuation of unfinished repair round 2/2; no budget reset, no third round, no publication. Issue3 remains OPEN. Only this isolated backend is writable. No original repositories, live HA, peer Card or frozen contract changes.

## Recovery checkpoint
- Frozen contract and wire read in full; SHA256 matches 6edd0bfde7c2405dcea691432536af425afd3e47522d7ab94e03477629c1d310 / 32fad886199a9c8bde3f2fc3366074260914ddb68d45c6b858f1532843fa576c.
- Historical R2 RED remains in nativefixtures/round2-red, round2-red-budget, round2-red-admission. Assertions unchanged. Historical regression-initial 295 is NOT current-byte acceptance.
- Read actual partial bytes, not rerunning one-shot tools/p3c_round2.py. Its edits through mix.validate_sources landed; remainder did not. Existing queued generation check, reset outcome reset, accepted flow bounds, resource-before-weekday and v5 descriptors retained.
- Prepatch actual mix.py/flow.py/gate source copies and hashes saved in nativefixtures/r2-recovered-prepatch. Directory has no .git; git status unavailable (not a repository); use exact byte snapshots/diffs instead.
- Remaining repair: mix event/admission/start accepted settings and durations; refill accepted high/timeout and cleaning reset; flow admission minimum must use accepted/hot-tightened bounds.
- Native runs pending. Will use new r2-recovered-* labels with explicit P3A/P3B sealed Card interpreter bindings. Sealed P3b is regression reference, NOT S5 shipped consumer acceptance.

## Completed R2 recovery (supersedes pending checkpoint above)
- Finished mix accepted-bound source/event/start settings and duration, refill accepted high/timeout plus cleaning reset, and admission minimum from accepted/hot-tightened flow bounds. Retained earlier partial queued-generation revocation, reset global outcome, resource-before-weekday and exact v5 descriptors. Did not rerun one-shot editor.
- First recovery run `SDK tools/p3c_native_gate.py r2-recovered-focused tests/test_p3c_flow.py`: CHILD_EXIT 1, 21 passed / 1 failed. Reset case exposed emergency latch overwritten by a concurrent stage `revoked` exception. Raw/source/receipt retained. Corrected existing mix/nutrient run exception boundary to retain already-latched fault, preserving closed fault setter; unchanged reset assertions now pass.
- Preserved 87 preformat input files and hashes in `nativefixtures/r2-recovered-preformat`; exact preformat→final diff in `nativefixtures/r2-recovered-final-static/preformat-to-final.diff`. Formatting/import cleanup affects control.py, flow.py, flow_settings.py, mix.py, nutrient.py, p3c_projection.py, services.py, tests/test_p3c_flow.py and tools/p3c_native_gate.py. Removed only dead unused test locals; retained explicit fixture re-export and all behavior assertions.
- `SDK tools/p3c_native_gate.py r2-recovered-final-focused tests/test_p3c_flow.py`: CHILD_EXIT 0; **22 passed**, no skipped, 5 dependency deprecation warnings; 23.02 seconds. Includes original five R2 cases, first path service/switch, original v4 rejection and round1 cases.
- `SDK tools/p3c_native_gate.py r2-recovered-final-full tests`: CHILD_EXIT 0; **317 passed**, no skipped, 5 dependency deprecation warnings; 167.56 seconds. This is current-byte full suite, not the historical 295 claim. Focused cases are included in 317; do not sum counts.
- Explicit P3A_CARD_PYTHON and P3B_CARD_PYTHON set to Card SDK interpreter in gate. Build copies only sealed P3b Q-successor Card; no live peer read. Runtime pytest output reports Python 3.14.5 / pytest 9.2.0.
- Final static: `SDK -m ruff check custom_components tests tools/p3c_native_gate.py` exit0; `SDK -m ruff format --check custom_components tests tools/p3c_native_gate.py` exit0, **82 files already formatted**. Ruff 0.17.3. Receipt/raw outputs in `nativefixtures/r2-recovered-final-static/receipt.json`.
- Each native run has immutable build, raw.log, command/SDK/env bindings, source_before/source_after and child exit in receipt.json; both input_bytes_unchanged=true. Independently compared **106 backend inputs per run** against current owned bytes, all match, in `r2-recovered-final-static/verified-native-byte-binding.json`. Use this explicit nonempty cross-platform path comparison rather than receipt.json's initial current_matches_native_inputs field (initial slash-only filter could be vacuous on Windows).
- Contract/wire hashes still match frozen originals after final checks. No original repositories, frozen docs, historical evidence or sibling Card changed. No stage/commit/push/install/auth/site HA/deploy.

## Native capture handles for parent join
`nativefixtures/r2-recovered-final-full/build/uninus-nutriculture/p3c-terminal-service.json` and `p3c-terminal-switch.json` are real registered native four-stage terminal snapshots (schema5, 30 root keys, four completed records, physical OFF). Same captures also exist in final-focused build. They are inputs available for parent S5 join, NOT evidence that S5 shipped Card already consumed them.

## Explicit unwired / unverified
Original five R2 fixes and final-byte backend regressions complete within the same round2/2. Parent-owned S5 Card→native join, joint SPEC/quality and any unexecuted full-contract safety matrices remain separate gates. Sealed v4 Card bridge regression is not S5 acceptance. No full P3 claim or physical-device/onsite verification. Issue3 remains OPEN; no third implementation round authorized.
