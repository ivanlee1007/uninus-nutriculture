# Independent integrated P1 quality/security review

## Verdict: APPROVED

No critical or important findings, no reproduced P1 blocker, and no required repair. This approves the **complete hash-bound staged P1 candidate in both repositories**, including the parent's final README-only companion/roadmap and CI-status clarifications. It is a code quality/security approval, not authorization for a tag/release, HA deployment, live-site writes or hardware actuation. P2–P5 remain deferred under the unchanged DEVELOPMENT_PLAN.

SPEC prerequisite: independently read `nutriculture-spec-recheck.md` and its original review; SPEC PASS is established, B1 is closed. This separate review inspected actual staged production/test/configuration/documentation source rather than treating that verdict as quality approval.

## Candidate binding

Evidence root: `C:/Users/ivanl/.hermes/cache/scratch/nutriculture-quality-review-evidence/`.

- `manifest-final.json` records SHA-256 of every index blob and corresponding working file: **489 backend files and 163 Card files**, including immutable evidence archives. Its SHA-256 is `15cb7ffb7e42705ec7617017df767e59f6df22b4a070d2daa71ea26b45dbc5cf`.
- `verification.json` verifies the full inventory against the prior exact-index gate's manifests and materialized snapshots. **Only README.md in each repository differs from gate 02.** Every other staged file matches that gate's recorded SHA-256; every gate snapshot matches its historical manifest. Thus all executable, test, fixture, dependency, package and CI inputs are unchanged.
- The only changes during this review were the parent's disclosed README updates/staging. Both final READMEs are now exact index/worktree matches. No untracked candidate files were found. Every other index/worktree difference is LF/CRLF only; all eight differing Python files also have equal parsed ASTs. No executable drift was found.
- Backend `manager.py`: index `b931636e47ffddad3f971565526915a65ca31fd043929245111609662b4d3888`; working bytes `3dc48ecec534b7a9e9091933cf713156a7de6376e78ab634b7571fdb4b57b3e1` (EOL-only difference).
- Card JS, exact index/worktree: `e4b7d29962e10bbd9139a29923e2e4e35f21017714d04bb61474f5e40ea9ec25`.
- Final backend README, exact index/worktree: `08556c5872a2301bbc241e4119839c8b3c8ca3c868e5158d3afd9d03027dbd6b`.
- Final Card README, exact index/worktree: `9fd89c777649f16c45980eecd71cbdeb5c488f3495aa5d24f0719d0fc1859136`.
- Both authoritative DEVELOPMENT_PLAN copies, exact: `2dbbdea2dbf430d85a4b7b91c5646cfb45587c824e9652f1171477ed1b778100`.

## Quality/security conclusions

**Backend:** Reviewed every active module, config/options flows, lifecycle setup/unload, native Number metadata, registry ownership, source/freshness projection and associated tests. Writes validate the complete candidate before mutation, use a per-entry lock and recheck active/live/generation/ID/current native EntityComponent instance plus registry platform/entry/unique ID after lock acquisition. There is no await between final admission and options/state update. Reload/unload and stale identity defenses are supported by actual native tests. Options preserve unrelated/latest parameter values; source changes reload while freshness is read dynamically. The B1 finite-state projection retains ownership checks and omits unusable targets without inventing IDs.

Persistence is intentionally **native scheduled ConfigEntry save**, not fsync/crash durability; normal final-write/fresh-process restart evidence is correctly distinguished. Source invalidity still permits tuning healthy Numbers by design. Strict units, last_reported freshness, periodic expiry, stable bounded reasons, shadow-only mode and permanently false irrigation readiness match P1. No output platform, MQTT client, custom actuator service or physical-control dispatch exists.

**Card:** Reviewed the full single shipped JS, editor, demo and tests. Dynamic title/units/reasons/errors render through textContent, not HTML interpolation. The sole write uses `number.set_value` with the explicit mapped ID and captured finite value. Missing/incompatible status, malformed/missing/unavailable targets and invalid metadata fail closed. Drafts and transport ownership are separately fenced across mapping/configuration/disconnect changes; late results cannot reconcile new-scope drafts. The current backend provides ownership-derived mappings; the Card is not a substitute authorization layer for arbitrary HA entities. Native HA service authorization remains the host's responsibility. No token handling, storage, external fetch/CDN or credential import is present. Demo is explicitly simulated and isolated.

**Packaging/docs/CI:** Root JS/package/HACS filename and backend manifest are consistent with manual alpha delivery. Both read-only CI workflows use explicit runtimes, bounded job durations and no release/deploy job, secrets or untrusted event interpolation. Active lint/test scope excludes immutable historical snapshots rather than rewriting proof. README changes accurately link companions/roadmap and defer exact-commit remote status to Actions. Historical handoff/test documents are evidence of their authors' local stages, not claims that remote CI or live UI acceptance happened. Private-HACS, Windows-native isolation, unmatched local/CI runtime matrix and live/authenticated-host limits remain explicitly disclosed.

**Credential safety:** Scanned all staged files, including archived source/logs, for credential assignments, JWT/private-key material and selected unsafe execution/storage/network sinks. `static-scan.json` has three matches, all documentation saying *no localStorage*; no executable sink or credential match. Manual production/CI review also found no credential origin/exfiltration path. This is source review plus targeted scanning, not a guarantee that regex silence proves universal secret absence. No vault, farm credentials or live HA were accessed.

## Actual executions and reused evidence

### New independent executions

1. `native_probe.py`, using existing backend Python/Core installation and the **exact staged gate-02 snapshot** in fresh scratch HA, exit 0. `native-probe-result.json` explicitly asserts all four checks true:
   - A stale open native Options form preserves a subsequent accepted Number write when submitted.
   - Cancelling a queued write changes no options; the lock recovers and a subsequent real native service succeeds.
   - Native Options abort changes no options.
   - The only observed services are two `number.set_value` events.
   This is three additional behavioral scenarios plus their service-safety assertion, not four pytest cases or a new full-suite run. Raw output: `native-probe.log`.
2. Fresh active backend Ruff check and format-check: exit 0, `All checks passed!`, `20 files already formatted`. Both repositories' `git diff --cached --check`: exit 0.
3. Full index/worktree/gate-snapshot hash and AST verifier: exit 0; final counts/README exceptions asserted programmatically in `verify.py` and `verification.json`.

### Reused only after consumed-input binding

- `nutriculture-index-gate-02/uninus-nutriculture.log`: **59 passed, five external warnings, 32.68 seconds**, actual native Core/Python 3.14.5 run of exact index bytes. Not rerun here.
- Gate-02 Card `test-results/exact-index/result.json`, raw logs and snapshots: native Node 18.6 syntax plus **5 unit tests**, real Chromium **16 browser tests**, no skips, exit 0; browser run 13.621 seconds. Geometry 320/768/1200: zero overflow/outside nodes. All nine consumed-input hashes match current candidate. Not rerun here.
- SPEC recheck bridge-result: separately asserted **all nine checks true**, including B1 omission, real service/readback, pair rejection, all ten writes, quality changes, rename and shadow/no-output. The recheck report records 15 browser payloads/native service events, only number.set_value. This quality review verified the existing checks and source equivalence; it did not execute another bridge or add overlapping test totals.

Remote Ubuntu CI (including Card Node 22/Python 3.13), hassfest/public HACS, authenticated HA websocket/dashboard-host acceptance, live farm/hardware and abrupt-power-loss durability were **not executed or approved**. These are disclosed delivery limits, not demands to implement deferred control phases.

## Reviewer artifacts and issues

Created only scratch collection/probe/verification scripts, source bundle, manifests, scan results, native probe HA directory/log/result and this report. No source edits, index changes, commit/history mutation, GitHub write or live HA action by the reviewer. Parent README staging is separately identified above.

One initial scratch collection command had a Python command-string SyntaxError before collection; replaced with a scratch script. No product failure or blocked probe resulted. No repair loop was consumed.

Reproduction handles: probe SHA-256 `ade9a6f80b6300923c33bb0a0b9dc97b8bc1be6f45b4428b2b56f0f39c89da98`; verifier SHA-256 `d4b15a5920b57d3db18c73d39f0802efdea3fbf4455b363c011079b9ab4e694b`. Original SPEC and gate evidence remain unchanged.
