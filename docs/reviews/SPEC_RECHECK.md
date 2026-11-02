# Independent integrated P1 SPEC recheck

## Verdict: SPEC PASS — B1 closed; full corrected P1 slice approved for SPEC

This bounded independent recheck composes the completed unchanged SPEC conclusions in `nutriculture-spec-review.md` with the corrected backend projection and a fresh execution of the original shipped-Card/native-HA bridge. There are no remaining SPEC blockers. Advance to the separate quality/security review; this report does not issue that review's approval or authorize deployment/live HA/hardware.

## Candidate and scope binding

Reviewed current working files, not merely HEAD/index. `nutriculture-spec-recheck-evidence/verification.json` records the complete tracked/unignored non-evidence candidate SHA-256 inventory for both repositories, changes against the prior review's raw inventory, commands, actual exits, archive receipt comparisons, and preservation assertions.

- Only production executable change: backend `custom_components/uninus_nutriculture/manager.py`, SHA-256 `3dc48ecec534b7a9e9091933cf713156a7de6376e78ab634b7571fdb4b57b3e1`.
- Test change: `tests/test_identity.py`, SHA-256 `a9807122cce1a78c941cc0d163fa7e17fdfbedf0c416ddffe660aafafe91d4ad`; existing AST nodes/assertions are preserved and seven parameterized native omission/recovery cases are appended.
- All other production, test, fixture, workflow and test-configuration files match the prior review's raw hashes. No prior inventoried non-evidence file is missing. The Card executable is unchanged, SHA-256 `e4b7d29962e10bbd9139a29923e2e4e35f21017714d04bb61474f5e40ea9ec25`.
- Other inventory differences are backend `.gitattributes` (already recorded as parent-owned packaging drift by the original report), backend README/TESTING/P1_HANDOFF, and companion P1_HANDOFF. Documentation now explicitly scopes the backend versus companion Card and permits intentional partial target maps; no schema expansion or deferred P2–P5 behavior was introduced.
- Candidate bytes remained unchanged during this recheck. The original report and every original reviewer-evidence file were hashed before and after: all unchanged. No source edits, staging, commit, GitHub or live HA access by this reviewer. Parent staging can change independently; approval binds working-file hashes rather than index state.

## B1 closure and adjacent cases

Inspected the complete production delta against the previous executed snapshot (`manager.py.diff`). `Tank.targets()` retains registry lookup by Number domain/platform/entry unique ID, current registry ownership, disabled-state rejection and missing-state rejection. It additionally requires a state convertible to a finite float. Unavailable, unknown, nonnumeric and nonfinite states are excluded without changing parameters/options or inventing entity IDs. This is a localized advertised-target correction, not a write-authority, persistence or service-contract change.

Fresh independent executions, existing native environment (Core 2026.10.4, CPython 3.14.5), isolated scratch HA only:

| Gate | Actual result | New evidence |
|---|---|---|
| Original reviewer bridge, copied byte-for-byte into a new directory (relative output paths change naturally) | Exit 0; **all nine reported checks explicitly asserted true** | `bridge.py`, `bridge.log`, `bridge-result.json`, `verification.json` |
| Native identity tests | **11 passed**, no skips, five upstream deprecation warnings, 6.72 seconds, exit 0 | `identity.log` |
| Wrapper verification | Exit 0; all bridge checks true, actual subprocess exits zero, original artifacts unchanged, candidate unchanged, old test nodes preserved | `verification.json` |

The exact original unavailable counterexample now publishes a status `parameter_entities` map without `ph_low`; the shipped Card remains blocked for that row. This is a real ConfigFlow-created integration, native registry/platform/StateMachine and actual published status sensor, not a replacement projection mock.

The native focused run additionally verifies unavailable, unknown, NaN, positive/negative Infinity, nonnumeric and missing states. Every case omits exactly the affected target while retaining other mappings, restores the same real Number ID through the actual Number's native state write, and proves parameter/options preservation. Existing rename/disable/delete queued-identity checks and metadata/missing-target checks also passed.

The unchanged original bridge re-exercised real shipped JS with Chromium and native ServiceRegistry transport: actual metadata step rejection; successful persisted/readback save; native cross-bound rejection with retained draft/options; all ten valid single-item writes; quality recomputation both directions; renamed registry target; corrected unavailable omission; Card blocking; shadow-only/no-output invariant. It observed 15 Card payloads and 15 service events, exclusively `number.set_value`. Importantly, the bridge itself is only a diagnostic collector: this recheck separately inspected and asserted **every check true**, rather than treating its exit 0 alone as approval.

## Preserved repair evidence and reuse

Inspected repair raw RED/GREEN and full-native receipts/logs:

- `11-target-red`: exit 1, six failed/five passed; only manager bytes differ from current, exactly as expected for pre-repair behavioral RED. Missing-state was already passing, not falsely claimed as a new RED.
- `11-target-green`: exit 0, 11 passed. All 26 receipt input hashes equal current files.
- `12-target-full-native`: exit 0, 59 passed/no skips, five warnings, 30.64 seconds. All 26 receipt input hashes equal current files. This full-suite result is verified existing evidence, **not** a new independent full-suite execution in this recheck.

Reuse the original completed review's native ConfigFlow/options rebinding, entry identity/isolation, ten defaults/metadata/validation, persistence/restart, sources/units/freshness, lifecycle/no actuation and schema-1 shadow conclusions. Reuse its unchanged Card syntax/unit/browser, input/draft/fence/duplicate-flight/safe rendering/editor/geometry conclusions. The prior independent runs were 52 native tests, five Node contract tests, 16 browser tests, and geometry at 320/768/1200; those were not needlessly repeated here. The corrected full native archive and fresh affected tests/bridge cover the localized changed contract. Overlapping counts are not added.

P2–P5, grouped atomic edits, physical pumps/sequencing/scheduling, emergency control and live irrigation permission remain deferred. This is isolated native/browser interoperability, not authenticated websocket/UI-host acceptance, farm integration, crash-durability proof or deployment acceptance.

## Artifacts

New scratch-only report: `C:/Users/ivanl/.hermes/cache/scratch/nutriculture-spec-recheck.md`.

New evidence: `C:/Users/ivanl/.hermes/cache/scratch/nutriculture-spec-recheck-evidence/` (bridge copy/results/log, focused test log and temporary native config, original-to-current code/test diffs, hash inventory/verification).

New execution driver: `C:/Users/ivanl/.hermes/cache/scratch/nutriculture-spec-recheck-run.py`.

No product issues or harness failures encountered in this recheck. Original FAIL report and counterexample evidence remain immutable historical records; this report supersedes only their open B1 verdict for the corrected hash-bound candidate.
