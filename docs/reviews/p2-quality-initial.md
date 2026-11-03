# P2 independent QUALITY / SECURITY review

## Verdict: REQUEST_CHANGES — one concrete safety must-fix

The frozen P2 scope is respected. This is not a P3 feature request, hardware watchdog requirement, architecture rewrite, or a reopening of the completed SPEC review. No repository files were written by this reviewer; no commit/push/deploy, credential read, or external HA connection occurred.

## Reviewed identity

Repositories: `D:/UNiNUS Projects/AI project/uninus-nutriculture` and `D:/UNiNUS Projects/AI project/uninus-nutriculture-card`.

Verified SHA-256 of both working bytes and staged Git blobs:

- `custom_components/uninus_nutriculture/control.py`: `944a26cfb67b53d63fee390aa3bb54e41ed886d58177458641b03c739d21b2d5`
- `uninus-nutriculture-card.js`: `04304bc0f62c5a26bbaa4a28018543a0ab46728e5148c44f1f2e221bb4a8d25f`

Full per-file worktree/index fingerprints for production and active tests/config are in `p2-quality-independent/source-manifest.json` beside this report. The actual controller copies consumed by both initial isolated native HA instances were independently hashed and equal the reviewed controller exactly. The ten raw mismatches against the historical native run receipt are CRLF/LF-only: LF normalization reproduces every corresponding receipt SHA. No executable drift was found in this comparison.

Initial repository checks showed no unstaged/untracked files. Later checks observed parent-side documentation/evidence work: both `docs/P2_ACCEPTANCE.md` became unstaged, with backend SPEC recheck evidence/report becoming untracked. These are disclosed, not treated as product defects or reviewer modifications; the reviewed controller and Card stayed equal to their staged blobs.

## Must-fix Q1 — necessary-source invalidation is silently forgotten during in-flight ON

**Severity:** high, refill safety / asynchronous lifecycle.

**Location:** backend `custom_components/uninus_nutriculture/control.py:124-126`, with event dispatch at `116-122` and admission continuation at `293-302`, `317`.

`changed()` schedules `evaluate()` for necessary-source events while `running` is true, including the `starting` phase. However, `evaluate()` immediately returns unless `flow_state == 'refilling'`. Consequently, a necessary sensor can become invalid while an admitted `switch.turn_on` is pending, with the actual output already ON, and this invalidation neither latches a fault nor revokes the admitted generation. If the source recovers before the provider coroutine returns, the final snapshot at line 298 is valid and the original request succeeds, entering `refilling` without ever dispatching OFF. The safety incident is lost permanently, not merely delayed by one timer tick.

This violates the existing P2 requirement that an invalid necessary source during an active run stops that run (`docs/P2_CONTROL_CONTRACT.md:18`, plus the pending-ON cleanup semantics at line 21). The controller already marks `running=True` before invoking the provider. A physical effect can precede a provider/API return; it is not safe to exempt this phase from source-invalid revocation.

### Real native reproduction

Independent probe uses the existing native HA `control_hass` fixture, commissioned Options, and native `switch.turn_on` routing for the shipped flow-run switch. It does not replace service routing or modify production/source tests. The fixture hardware blocks its ON coroutine at an explicit barrier; the probe sets its fake-hardware ON state before releasing the provider return, modeling applied output with delayed API completion.

1. Commission and enable master/refill.
2. Start through the native flow-run switch; wait until hardware ON handler has entered.
3. Publish fake-hardware output ON while its service coroutine remains pending.
4. Set `sensor.ph = unavailable`; allow production event tasks to run for 100 ms.
5. Restore `sensor.ph = 5.6 pH`; allow its event tasks to run, then release provider completion.
6. Observe successful native call, `flow_state='refilling'`, `fault=null`, physical output `on`, and only `['turn_on']` in hardware calls.

Observed twice on this exact controller:

```json
{"recover":true,"during_invalid":{"state":"starting","fault":null,"output":"on","calls":["turn_on"]},"after_return":{"result":"NoneType","state":"refilling","fault":null,"output":"on","calls":["turn_on"]}}
```

`NoneType` here is the successful response of the native switch service, not a fabricated success receipt. The assertion requiring rejection and OFF failed in both executions.

### Adjacent controls

- Leave the source invalid until the pending ON returns: existing post-await admission rejects with `ServiceValidationError`, faults, and performs `['turn_on','turn_off']`; **PASS**.
- Apply the same transient invalidation/recovery after normal start has reached `refilling`: the controller correctly latches `source_invalid`, output becomes OFF, and does not resume after recovery; **PASS**.

Thus the counterexample is specific to the starting/in-flight-I/O phase, not an unavailable-sensor fixture failure or a requirement invented for all source flicker.

### Minimal repair direction

During `starting`, observe necessary-source invalidity and latch/revoke the current admitted run before a later recovery can erase it. Preserve bounded pending-ON follow-up OFF and truthful running/fault state; do not simply remove the phase guard and apply the refilling-only `output != on` test to an output that has not yet acknowledged ON. The post-provider checks must reject the poisoned run and ensure OFF, even after sensor recovery. Keep the adjacent ordinary-start and late-ON cleanup behavior green. No new framework or P3 work is required.

## Commands actually executed and results

Environment for both native commands:

```text
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=D:/UNiNUS Projects/AI project/uninus-nutriculture/tests
```

Interpreter: `D:/UNiNUS Projects/AI project/uninus-nutriculture/.venv/Scripts/python.exe`.

Common command prefix (actual argument arrays are saved without ambiguity in the JSON receipts):

```text
<interpreter> -B -m pytest -p no:cacheprovider -p conftest
  -c D:/UNiNUS Projects/AI project/uninus-nutriculture/pyproject.toml -q -s
```

1. `--basetemp C:/Users/ivanl/.hermes/cache/scratch/p2-quality-independent/native-temp C:/Users/ivanl/.hermes/cache/scratch/p2-quality-independent/test_quality_start_source.py`
   - pytest exit **1**, **1 passed / 1 failed**, 4.82 seconds.
   - Exact command/exit: `p2-quality-independent/run.json`.
   - Raw output: `p2-quality-independent/native-probe.log`.
2. `--basetemp C:/Users/ivanl/.hermes/cache/scratch/p2-quality-independent/native-temp-adjacent C:/Users/ivanl/.hermes/cache/scratch/p2-quality-independent/test_quality_adjacent.py C:/Users/ivanl/.hermes/cache/scratch/p2-quality-independent/test_quality_start_source.py::test_invalid_source_during_applied_on_cannot_be_forgotten[True]`
   - pytest exit **1**, **1 passed / 1 failed**, 3.13 seconds.
   - Exact command/exit: `p2-quality-independent/adjacent-run.json`.
   - Raw output: `p2-quality-independent/adjacent-repeat.log`.

The outer capture commands exited 0 because they deliberately persisted and printed the subprocess result; both receipts retain the real pytest exit 1. The failure is the safety assertion, not import/discovery/setup. Warnings were HA/backoff deprecations, not blockers.

## Other reviewed boundaries / limits

Source-inspected the controller, Options/settings and registry identity/ownership checks, lifecycle setup/unload, auth/admission guard, native services/Switch/Button handlers, monitoring/control status projections, parameter/freshness manager, and shipped Card maps/events/Promise ownership. A production-only static scan found no literal-secret, shell=True/os.system, eval/exec, or pickle load matches. This is not a proof of absence of all security defects.

Read the exact-index gate summary, extension receipt, and native run manifest; historical 143 backend / 9 Node / 23 Chromium and real bridge results are pre-existing evidence, **not claimed as rerun here**. No browser rerun was necessary to establish this backend blocker. No additional concrete must-fix was established during the bounded source pass. Overall candidate is not approved until Q1 is repaired and independently rechecked.

Created only scratch report, independent probe scripts, logs/JSON manifest, and isolated native HA basetemp directories under `C:/Users/ivanl/.hermes/cache/scratch/p2-quality-independent/`.
