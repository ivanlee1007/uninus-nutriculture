# Independent integrated P1 SPEC review

## Verdict: BLOCKED — one concrete P1 contract defect

The shipped Card and real native HA backend interoperate successfully for normal P1 monitoring and single-item parameter changes. However, the backend still advertises an unavailable Number as a writable target. This violates the controller's explicit acceptance requirement that registry-derived Number maps omit disabled/deleted/unavailable targets. Do not advance to the separate quality/security approval gate until this is corrected and independently rechecked.

### B1 — unavailable Number remains in `parameter_entities`

- Location: `uninus-nutriculture/custom_components/uninus_nutriculture/manager.py:80–94`, specifically line 93. `Tank.targets()` requires only that a state exists; it does not check whether its state is `unavailable` (or `unknown`/otherwise unusable).
- Reproduction in a real isolated Core 2026.10.4 instance: create the entry via the native ConfigFlow, load the shipped platforms, then use the native StateMachine to set its existing registry-owned pH-low Number to `unavailable`, retaining its metadata. Drain native callbacks and inspect the actual published status sensor. The resulting `parameter_entities.ph_low` remains `number.reviewer_tank_ph_low`.
- Evidence: `nutriculture-spec-review-evidence/bridge-result.json`, `checks.unavailable_number_omitted: false`, plus `unavailable_target_map` and `final_status.attributes.parameter_entities`. The reviewer did not replace `Tank`, Registry, ServiceRegistry, or Number platform logic.
- The Card correctly refuses that unavailable Number; `checks.card_blocks_unavailable_number: true`. Thus this is a backend consumer-contract defect, not a demonstrated physical-output or Card miswrite. Its blast radius is limited by the Card's second gate, but the requested backend contract still is not met.
- Existing `tests/test_identity.py:41–66` tests missing state, not unavailable state; existing rename/disable/delete tests also do not cover this counterexample.
- Smallest closure: omit unavailable/unusable states from the projection, retain actual registry ownership checks, add native regression coverage for unavailable → omitted → healthy recovery, and rerun the affected boundary/bridge tests. No new service or architecture is needed.

## Inputs and independence

Read both controller-owned `docs/DEVELOPMENT_PLAN.md` copies; they were byte-identical. Reviewed production backend modules, shipped Card JS, READMEs, handoffs, test drivers and the native flow/service/lifecycle/validation/source/freshness/restart/safety tests. Reviewed actual evidence manifests and raw logs rather than accepting the handoff counts.

All reviewer-authored files are under `C:/Users/ivanl/.hermes/cache/scratch/`. No source edits, commit, push, release, live HA connection or hardware action was made. Tests ran only against fresh scratch HA configuration. No credentials were read.

- Backend `docs/evidence/10-final-native/run.json`: all 26 recorded current input hashes matched.
- Card `docs/evidence/final-package-gate/result.json`: all nine recorded current input hashes matched.
- Both repositories initially contained untracked candidate files. Parent staged them while this review ran. Independently inspected 32 staged production/test/config cells: no non-EOL differences against the executed working files; Python ASTs match for each Python comparison. Exact index/worktree SHA-256 pairs are in `index-verification.json`.
- The pre-review inventory's only detected content drift was parent-owned backend `.gitattributes`, consistent with the parent's packaging update. Executable source/test bytes did not drift. This is not a claim that every repository byte equals the parent's separately materialized snapshot.

## Checks actually executed by this reviewer

Evidence directory: `C:/Users/ivanl/.hermes/cache/scratch/nutriculture-spec-review-evidence/`.

| Check | Actual result | Evidence |
|---|---|---|
| Backend native suite, existing venv, fresh scratch basetemp, cache plugin disabled | 52 passed, five external deprecation warnings, exit 0, 30.20 seconds | `pytest.log` |
| Native Node syntax and contract unit suite | Node 18.6.0; five tests, no skips, exit 0 | `card-gate/result.json`, `card-gate/unit.log`, `card-gate/syntax.log` |
| Existing shipped-JS real Chromium suite | 16 passed, no skips, exit 0, 12.174 seconds | `card-gate/browser.log` |
| Expanded Card geometry | 320/768/1200 viewport; actual Card widths 304/752/1184; zero horizontal overflow and zero outside nodes | `card-gate/browser/geometry.json` and screenshots |
| Reviewer-authored shipped-browser/native-HA bridge | Eight positive checks passed; unavailable-target omission check failed | `bridge.py`, `bridge.log`, `bridge-result.json` |
| Hash and staged-input verification | Historical consumed-input hashes match; no executable non-EOL differences | `before.json`, `index-verification.json`, `verification.json` |

Backend command: `.venv/Scripts/python.exe -m pytest tests -v -s -p no:cacheprovider --basetemp C:/Users/ivanl/.hermes/cache/scratch/nutriculture-spec-review-evidence/pytest-temp`, with `PYTHONDONTWRITEBYTECODE=1`.

Card command: `.venv/Scripts/python.exe tests/check.py --evidence C:/Users/ivanl/.hermes/cache/scratch/nutriculture-spec-review-evidence/card-gate`, with the existing installed Chromium selected through `CHROMIUM_EXECUTABLE`.

Bridge command, run from backend repository: `.venv/Scripts/python.exe C:/Users/ivanl/.hermes/cache/scratch/nutriculture-spec-review-evidence/bridge.py`.

The bridge is a diagnostic collector: its exit 0 means the collection and positive assertions completed, **not** that all its reported checks passed. The false omission check is deliberately retained as the blocking counterexample. Initial bridge attempt failed before setup because the reviewer guessed an unavailable `homeassistant.util.json.json_dumps` import. That harness error is preserved in `bridge-attempt1.log`; the corrected scratch-only serializer then completed. It is not a product failure or behavioral RED.

## Integrated boundary actually exercised

The original Card suite uses a simulated `hass.callService`; it does not itself establish native backend interoperability. This reviewer closed that evidence gap with a real Chromium page importing the repository's actual root JS and real HA-produced state/metadata snapshots. Actual button listeners emit `callService(domain, service, data)`. A Playwright exposed-function transport passes those same three arguments to native `hass.services.async_call(..., blocking=True)`, then supplies the actual StateMachine readback or native error to the Card. No permissive service mock or copied business logic is used.

Observed 15 actual Card payloads and 15 corresponding native service events, exclusively `number.set_value`; no switch or other service calls. Among them:

```json
["number", "set_value", {"entity_id": "number.reviewer_tank_ph_low", "value": 5.5}]
["number", "set_value", {"entity_id": "number.reviewer_tank_ph_low", "value": 5.9}]
["number", "set_value", {"entity_id": "number.reviewer_renamed_ec", "value": 0.82}]
```

- Real backend pH metadata advertises step 0.1. The Card correctly blocks 5.55 before transport, unlike the existing permissive browser fixture's step 0.01. This fixture discrepancy is not a production incompatibility.
- 5.5 is accepted; native Number/options/status read back 5.5.
- 5.9 for pH-low conflicts with high 5.8; native validation rejects it, all persisted parameter options remain unchanged, and the actual Card retains its 5.9 draft plus failure message.
- Every one of the ten actual registry-derived targets accepts an individually valid Card save; the complete status parameter map equals the real options map.
- Changing pH-high across current pH 5.6 changes native quality to `out_of_range`, then restoring it changes quality back to `within_range`.
- A native registry EC-low rename changes the advertised target, and the subsequent actual Card payload uses `number.reviewer_renamed_ec`.
- Shadow mode and `ready_for_irrigation: false` remain in force.

This is an isolated ServiceRegistry bridge, not authenticated HA websocket/UI-host acceptance, real farm integration, crash-durability proof, or deployment approval.

## Remaining contract assessment

The reviewed source and actual native/Card tests support the rest of the P1 delivery: native ConfigFlow and Options rebinding; entry-ID identity and same-name tank isolation; ten defaults/units/bounds/steps; finite-value and strict low/high validation; ConfigEntry-options persistence with normal fresh-process restart; inclusive quality ranges; strict source units; source deletion and invalid values; `last_reported` freshness with periodic expiry; no actuation; schema 1 shadow attributes and permanently false irrigation readiness. Card tests cover safe text rendering, metadata-derived single-item saves, rejected-save drafts, live telemetry caret/node retention, mapping/config/disconnect fences, duplicate-flight protection, missing/incompatible target gates, editor/picker and responsive geometry.

P2–P5 remain explicitly future work. Grouped atomic edits, pumps, sequencing, schedules, emergency-control behavior and live irrigation permission are not silently included as P1 requirements.

Documentation clarity, nonblocking: backend README line 80 and handoff line 38 say there is “no custom Card.” This is true only of the backend repository, but reads incorrectly as a whole-product statement now that the companion repository exists. Clarify repository scope and link/name the companion Card rather than implying P1 uses only native Entities cards. Card handoff line 12's demand for a “complete” mapping should likewise acknowledge intentionally omitted disabled/deleted/unavailable targets; the Card implementation already handles partial maps safely. No need to change the frozen schema for either clarification.

No separate quality/security PASS is issued: this was SPEC-first review and B1 remains open.
