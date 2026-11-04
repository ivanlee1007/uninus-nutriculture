# P3a safety B1 handoff — bounded gap1–3 repair

2026-11-03. **Partial safety hardening, NOT complete P3a approval, NOT release/deployment or physical acceptance.** Parent bridge already green is separate evidence and was not rerun/modified here.

## Verified current result

- `p3a-a2b-18-final-regression`: actual child exit0, **197 passed**, 5 upstream deprecation warnings, 67.17s. Includes original174 plus23 new native cases; focused counts overlap and must not be added.
- `p3a-a2b-17-focused-green`: exit0,23 passed. Ruff check on all five owned changed Python files passed after narrow formatting/import cleanup.
- Exact current source/test bytes match final18 receipt snapshot, programmatically verified. `docs/evidence/p3a-a2b-18-final-regression/readback.json` holds all nine fingerprints and unchanged-frozen verification. Sensor/switch/__init__/test_p3_wire bytes equal A2-28 snapshot. Original first native pulse test assertions retained; fixture only adds controlled barriers/failure flag.
- No SDK helpers/global monkeypatch changes; native ServiceRegistry, SwitchEntity, AuthManager and EntityRegistry exercised. No parent bridge/Card/common contract/A1 configuration edits; no stage/commit/push, credentials, HA network, version or release changes. Preexisting dirty tree preserved.

## Changes

- `control.py`: controller remains sole physical service owner. Each ON obtains fresh active-admin/internal authorization; after authorization checks active entry/runtime identity, generation, current stage gates, sources and original Registry bindings, resolving current names rather than trusting cached IDs. Final weekday check is immediately before stage-first circulation ON; later pump openings do not reapply weekday. ON ACK completion revalidates again. Safety OFF retains internal causal Context and resolves original captured identity, never a reused foreign name. Registry identity invalidation now wakes/revokes running nutrient stage. Finished-stage pending-I/O retains nutrient stop routing and rejects restart as busy.
- `nutrient.py`: pending circulation ACK is monitored for captured invalid/danger events instead of blocking unconditionally. Event payload unit invalidity, low level, dangerous EC/pH, circulation OFF/unknown and current-pulse midpoint crossing are latched despite immediate restoration. Both role OFF attempts execute independently; one failure cannot skip the other. Serialized cleanup retains running/ownership on failure or pending I/O; late ON settling during another role's OFF ACK causes another cleanup pass. Late completion after stage exit reenters owned cleanup.
- `tests/test_p3_dosing.py`: adds optional on_apply_gate/off_ack_gate/fail_off to existing fixture; existing on_ack_gate, outputs/calls/rows and independent3s local cutoff contract preserved. Device cutoff never counts as native OFF.
- New `tests/test_p3_dosing_admission.py` (10 native cases) and `tests/test_p3_dosing_io.py` (13 native cases).

## Behavioral evidence chain

All labels are new; old A1/A2/parent bridge evidence untouched. Each completed receipt contains exact pre-run source/test bytes, SHA, command, raw log and child return code.

-01 RED pending circulation invalid→recovered fails native OFF0.75s; -02 GREEN1.
-03 RED4 event failures (wrong unit, midpoint transient, recovered circulation OFF/unknown), other4 already green probes; -04 GREEN8.
-05 outer timeout124: initial runner held raw log in pipe; snapshot exists but no completed raw/receipt. **Incomplete run, not behavioral RED.** A broad native drain with held ACK was the synchronization problem. Switched to file-backed owned-process-group runner in scratch;90s bound/taskkill only owned tree, retains raw logs.
-06: AuthManager fixture missing setup caused5 setup errors, plus genuine rename failure. Not auth behavioral RED. -07 initializes real AuthManager and shows6 genuine behavioral failures (delete/demote/inactive/generation/entry after circulation ACK; Registry rename). -08 GREEN14 including event probes.
-09 RED1 nutrient OFF failure skipped circulation;2 late-physical-ON cases already green. -10 GREEN17. -11 intermediate full191 GREEN.
-12 RED1 late ON during other role's OFF ACK fails convergence; foreign-name reuse probe already green. -13 GREEN13 I/O cases.
-14 RED2 circulation ACK revocation when EC already high/no pump needed. -15 **actual GREEN2 despite the `postack-fault-red` label**; added fault/master assertions were already satisfied, no invented RED.
-16 RED1 Registry removal must revoke automatically, not wait for manual stop. -17 GREEN23, also verifying weekday changed while admission held versus already physically started. The weekday probes are already-green supplementary checks, not new RED.
-18 final full197 GREEN. Wrapper commands sometimes included follow-on progress writes; receipt `returncode` is authoritative child outcome (e.g.-12 tool wrapper exit0 but child exit1).

## Remaining gaps / next bounded tranche

**Do not close entire gap1–3 matrix yet.** Current concrete repairs are green, but this25-minute tranche did not exhaust:

1. Deterministic revocation *inside* an actually suspended auth lookup for each first/subsequent opening; current native tests revoke during physical circulation ACK and use an owned adapter barrier for final weekday admission. No SDK monkeypatch used. Full runtime replacement/source-change/Registry remove-recreate combinations at each await remain.
2. Symmetric two-role late OFF/provider-failure order permutations, simultaneous duplicate stop/cleanup callers, and hard deadlines/cancellation/lifecycle interplay. Tested both role late physical ON after stop, N OFF failure with circ best effort, one cross-role held OFF-ACK overlap, identity loss/reuse and truthful quarantine; not the full Cartesian matrix. Busy/idempotent/finished-stage routing production tightened, but isolated new RED was not independently established for every ancillary branch; two lateON probes were already green before cleanup repair. Preserve this distinction for review.
3. Circulation state loss/units/min/danger transient tests exist; expanded both-role identity-loss, callback ordering and arbitrary event bursts still need bounded coverage.

A2 handoff gaps4–9 deliberately deferred, not silently approved: elapsed send→confirmedOFF conservative accounting and stage ec_timeout/deadlines during ACK; monotone hot-tightening vs relaxation; complete sample/stability/token/burst matrix; real Core STOP/unload/repeated cancellation and idle emergency/reset danger checks; replay cap/stage projection; high-pH timed alarm and explicit resource leases. Existing rejection of known shared outputs is not a proven lease mechanism. No physical hard-limit guarantee follows from the fixture.

## Exact final production/test hashes

```
control.py                  6c109df72e49cbc14e996d5bad6652e888e9a41d39350e7bf8e34db39e6ea148
nutrient.py                 2e3554c3dc63d172224d4edf0c7803e643afe882d5ef9a5bda92b6cfd1758e25
test_p3_dosing.py            2124273ca2b8da3a055261e5a0543af1301114a5e901a47fc7ab89271e61212b
test_p3_dosing_admission.py  73c57808acba7808061a5925df826490b83da54e0adf06bc49ff40fa52383d34
test_p3_dosing_io.py         f36d9491828ff9b625f6254d749d1b48dace86dfe5cfd4cf1f6c799efcc78135
```

Continuous checkpoint: `C:/Users/ivanl/.hermes/cache/scratch/nutriculture-p3a-safety-b1-progress.md`. Scratch bounded runner: `p3a_b1_evidence.py`; actual full commands appear per receipt. Parent should independently inspect patches and finish residual bounded safety matrix before SPEC/quality/release decision.
