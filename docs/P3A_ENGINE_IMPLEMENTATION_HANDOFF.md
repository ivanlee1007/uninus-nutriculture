# P3a A2 engine implementation handoff — partial safety matrix

Date: 2026-11-03. **Native nutrient path connected; NOT complete P3a safety acceptance, NOT release/deployment approval.**

## Exact current verification

- `.venv/Scripts/python.exe tools/evidence.py p3a-a2-28-final-regression tests -q --tb=short`: actual child exit **0**, **174 passed**, five upstream deprecation warnings, 61.78s. This is the current full suite, not the historical A1 159 count. Focused runs overlap and must not be added.
- Ruff check passed for `custom_components/uninus_nutriculture` and changed P3 tests. Owned files formatted. No global install.
- Final receipt timestamp `2026-11-03T11:26:07.323049+00:00`; exact current six owned source/test hashes independently matched receipt snapshot (`snapshot_matches: true`). Every p3a-a2-02 through -28 receipt retains pre-run source/test bytes, SHA256, command, raw output and child exit; -01 historical RED untouched.
- No Card edits, no parent bridge edits, no HA network/credentials, no stage/commit/push/tag/deploy. All preexisting A1/P2 dirty/untracked files preserved. No manifest/version/README changes.

## Files this worker changed

- `custom_components/uninus_nutriculture/control.py`: native nutrient admission/enable/persistence/start/stop routing, internal physical adapter (only Controller calls physical service), scoped state-reported listener, nutrient-only restart output checks and reset.
- New connected `custom_components/uninus_nutriculture/nutrient.py`: native circulation/pulse/OFF/mix/new-sample/stability loop; entry background owner; tracked shielded output calls; bounded feedback wait; cleanup survives run cancellation.
- `switch.py`: per-entry native nutrient availability/state.
- `sensor.py`: actual native nutrient map and stage projection without refill=dosing.
- `tests/test_p3_dosing.py`: retained original vertical test and extended fixture/15 native cases. Fixture `outputs/calls/rows` API unchanged; Output adds optional `on_ack_gate` solely for delayed-ACK tests. Existing fake nutrient 3s local cutoff remains, never accepted as native OFF proof.
- `tests/test_p3_wire.py`: narrow A1 unsupported expectation evolved after the real path went GREEN; original historical bytes preserved in receipts.
- This handoff and immutable new evidence directories; progress continuously saved to `C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-engine-progress.md`.

## Proven behavior / RED→GREEN history

- Original -01 RED -> -04 native pulse GREEN: nutrient-only entry without refill binding, native master/nutrient Enable produces zero output; real `start_flow` receipt; circulation before pump; EC0.85 switches pump OFF within0.75s during2s pulse (not fake3s cutoff); required1s mixing keeps circulation; new EC0.86 after barrier completes; releases circulation; irrigation false.
- -02 exposed P2 parameter listener using absent refill bounds during nutrient `starting`; -03 exposed binary float midpoint0.8500000000000001. Both failures retained; Decimal midpoint corrected actual0.85 boundary.
- -05 RED -> -06 GREEN: pulse OFF deadline starts at send, not delayed ON ACK; running stays true while ON unsettled.
- -07 RED -> -08 cleanup cancellation failure -> -09 GREEN: invalid EC event during pending ON latches even when valid state restored in the same event-loop turn; immediate OFF; cleanup not lost to concurrent native OFF.
- -10 RED -> -11 GREEN: actual nutrient map + native availability and nutrient running/refill skipped projection. Per-entry P2-only still schema2/no nutrient map.
- -13 RED -> -14 GREEN: pending ON low level / danger EC / danger pH events latch despite immediate recovery and stop within0.75s.
- -15 RED -> -16 GREEN: maximum pulse count blocks another dose after a genuinely new low sample.
- -17 RED -> -18 GREEN: same-value native state-reported EC after sample barrier counts as a new operator-declared reported sample, zero-dose completion.
- -19 RED -> -20 GREEN: sequence/timestamp attribute repaint with unchanged token cannot complete; advancing valid token can.
- -21 RED -> -22 GREEN: nutrient-only native emergency stops both outputs, reset does not require refill binding and does not re-enable/restart.
- -23 RED -> -24 GREEN: reserved total-ON budget blocks another full dose after fresh low sample.
- -25 RED -> -26 GREEN: whole flow deadline expires while waiting for new sample, stops outputs rather than waiting the longer sample timeout.
- -27 RED -> final -28 GREEN: native reload checks both nutrient and circulation ON outputs, latches restart fault/master OFF without seizing externally ON output.
- Intermediate -12 full162 GREEN; final -28 full174 GREEN supersedes it.

## CRITICAL remaining implementation + safety TDD (do not ship)

This is a real connected execution slice, **not a finished safety engine**. Current tests do not establish the following and inspection shows concrete gaps:

1. **Every-ON reauthorization/generation/source/binding**: start authorizes, but background execution does not yet recheck admin/entry generation/identity after each await before all physical ONs. `targets` are captured entity IDs and are not re-resolved for each dispatch. Add delayed circulation admission/revocation/source/registry tests first. Weekday is checked before an authorization await, not at final stage-first-ON; recheck after awaited resource/admission. No awaited resource lease abstraction exists yet; commissioning rejects known sharing but explicit owned lease accounting still needed.
2. **Circulation pending/lost source safety**: pulse wait observes captured invalid/min/danger events, but pending circulation ON currently awaits feedback before validation, and running circulation going OFF/unknown is not latched/checked. Recovered unit-invalid events are not latched (numeric-invalid is); current snapshot catches only sustained wrong units. Midpoint transient crossing+recovery is reread, not latched. Add these RED cases.
3. **Late IO convergence/restart exclusion**: operations are tracked/shielded and callbacks retry cleanup after stage exits, but late ON/OFF ordering for BOTH outputs is not exhaustively safe/proven. Cleanup currently waits nutrient OFF before attempting circulation OFF; failed nutrient OFF skips circulation attempt. New start while `running=True` after prior stage task finished can return idempotent success; it must reject unsettled old operations. Stop on a finished nutrient stage with pending IO can fall through P2-only cleanup. Need bounded late-I/O matrix, duplicate cleanup serialization and truthful unknown/flow switch behavior. Do not infer hard physical protection from fixture cutoff.
4. **Budget/deadline completeness**: max pulses and full-pulse reservation enforced; **elapsed send→confirmed OFF conservative accounting is not yet included**. `ec_timeout*60` stage deadline missing. Whole deadline enforced in domain polling but not during feedback/ACK waits; tighten all dispatch deadlines without cancelling underlying I/O. OFF cleanup must retain independent bound.
5. **Hot settings**: safety group copied at admission, no hot tightening merge; midpoint currently reads live parameters and thus relaxation can extend a run. Add restrictive-vs-relaxation tests before implementing admitted monotone bounds.
6. **Sample/stability edges**: sequence/timestamp basic monotonic tokens and same-report mode implemented; malformed/old/future/token-mode matrices not fully covered. Stable>1 path currently can pulse after its interval before consuming the next post-barrier fresh sample if EC drops: fix sample consumption loop with explicit last-consumed tokens and minimum interval. Multi-event bursts, stale token after mix, attrs-only reported mode and invalid-token handling need targeted tests.
7. **Lifecycle/native safety**: emergency/reset/reload basic N-only path proven, but idle emergency with externally ON nutrient/circulation is not yet handled independently of refill. Reset checks numeric validity but not nutrient danger/min thresholds. STOP/unload/owner cancellation and repeated cancellation require actual Core lifecycle tests; internal OFF Context/deleted-user behavior exists via adapter but no new nutrient proof yet.
8. Request replay dictionary is time-pruned but nutrient branch lacks P2's64-entry cap. Busy/idempotence/config combination currently wired but no new nutrient-specific native test. Stage projection after enable changes/admitted-plan changes needs cleanup (do not derive historical stage owner solely from current nutrient Enabled).
9. High-pH timed alarm not implemented. Necessary mixing currently unaffected by independent unavailable mix switch, but explicit resource lease and independence tests remain.

## Parent integration boundary

`tools/p3a_dosing_bridge.py` is parent-owned and untouched; do not interpret this handoff as a bridge result. Parent can now execute its native/shipped-JS vertical path against the frozen final snapshot, but must retain incomplete-safety classification even if bridge passes. Fixture outputs/calls/rows remain compatible. No full Issue#3 acid/mix/flexible graph implementation is claimed. Independent SPEC/quality review must happen after remaining safety, not treat full174 as a release gate.

## Frozen final fingerprints

```
control.py          224460153d8f3b561f4b4f7bf9bc3c7469a2637de596e0fb18542ea594cbd90e
nutrient.py         b79bd7330b6216fb40a0af9a1875738b986496ec3fa925e340b97eea7571349c
sensor.py           2b103a2d89e9fac0410339c5a43eaeca464665d4fab427765597d0d3b55cd42c
switch.py           17724872b6dc1ddd2ad8f87603c78cccb485ebf372d8b6109927e1e5e35e7aeb
test_p3_dosing.py   2d83af7ed9ff244f96430f1fdc44196e428cc9218a64e45877e40d18cc84b855
test_p3_wire.py     74f93368b74ae79e9325d80747ce65b8063d6dea1e3af16ab5d3887c3a09741d
```
