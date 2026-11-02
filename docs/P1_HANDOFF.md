# P1 handoff — 0.1.0 alpha

## Delivered

- Installable `custom_components/uninus_nutriculture/`: native name/source config flow, source options, one stable entry per tank, 10 owned CONFIG/BOX Numbers and frozen shadow-status sensor.
- Finite/bounded/decimal-step and pair validation, per-entry serialization, lifecycle/registry-identity admission, scheduled native ConfigEntry options persistence, hot sibling/status projection.
- Inclusive pH/EC/level checks; source deletion/nonfinite/unit/age rejection; `last_reported`, real 5-second refresh and cleanup; exact registry-derived writable targets following rename and omitting disabled/deleted/missing/unavailable/unknown/nonfinite/nonnumeric states.
- No output mappings, MQTT client, buttons, control service dispatch or credentials. `ready_for_irrigation` remains false.
- `manifest.json`, strings and en/zh-Hant translations, private-HACS metadata, README in Traditional Chinese, pinned test requirements, Ubuntu Python 3.14 CI, git hygiene.

## Verified locally

**59 passed, 0 skipped** after bounded B1 repair, real Core **2026.10.4** / CPython **3.14.5**, plus compileall and Ruff check/format. Five external deprecation warnings retained. Native fresh-process storage round trip verifies all ten changed values, stable entry ID and renamed entity ID after actual Core final-write. Multi-entry, source event, native flow/service, invalid transaction, concurrent conflicting writes, unload/queued writes and registry lifecycle regressions included. Seven additional native target-state cases prove omission in the actual status sensor and recovery to the same actual Number ID without parameter/options mutation. Focused behavioral RED: 6 failed / 5 passed; GREEN: 11 passed. Missing-state coverage was already green, not a new RED.

Evidence handles:

- `docs/evidence/11-target-red/` and `11-target-green/`: raw focused RED/GREEN with exact pre-run snapshots and metadata.
- `docs/evidence/12-target-full-native/`: current 59-case native run, snapshots, metadata and static checks.
- `docs/evidence/10-final-native/`: original 52-case historical evidence, unchanged.
- `docs/TESTING.md`: honest RED/GREEN index, fixture errors and scope limitations.

Re-run on this host:

```sh
.venv/Scripts/python.exe tools/evidence.py independent-review tests -v -s
.venv/Scripts/python.exe -m compileall -q custom_components tests
.venv/Scripts/ruff.exe check custom_components tests tools/evidence.py
.venv/Scripts/ruff.exe format --check custom_components tests tools/evidence.py
```

Use a new evidence label for every independent run; the runner refuses overwrite. Linux uses `.venv/bin/python` and the same requirements file.

## Boundaries and pending independent review

- WSL cannot start (`HCS_E_HYPERV_NOT_INSTALLED`); native Core ran in a local Windows-only test venv instead. This is not an endorsement of Windows HA production deployment.
- Save acceptance means **native scheduled save**, not a verified fsync. Normal final-write restart tested; abrupt power loss not tested.
- Strict source units; **no automatic conversion**. EC µS/cm is rejected rather than treated as mS/cm.
- This repository contains the backend; the companion `uninus-nutriculture-card` repository already provides a P1 Card. This repair does not establish integrated P1 approval or repeat the reviewer browser/native bridge. No actuation or P2–P5 implementation. Full roadmap remains in README and controller-owned `docs/DEVELOPMENT_PLAN.md` (not edited).
- Remote Ubuntu CI, official hassfest/public HACS, live UI/hardware remain unverified. No commit, push, release or live-HA contact performed.
- Parent independent review is pending; any follow-up fix work should be bounded to at most two loops as requested.
