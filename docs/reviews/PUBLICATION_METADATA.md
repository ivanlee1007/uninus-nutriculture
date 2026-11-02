# Publication-equivalence metadata review

## Verdict: APPROVED — SPEC delta PASS, quality/security PASS

Scope: working/index metadata on backend HEAD `c38802d674289ab7a0db39ef77acc1f73a64c8d0` and Card HEAD `08191b329db23f662e74eeb24b6ab2ac50c81d17`. No production changes or new acceptance scope are approved by this bounded review.

## 1. SPEC delta

Read the prior independent SPEC recheck and quality approval first. Programmatically compared all original approved manifest entries (489 backend, 163 Card) against current index blobs and working bytes. The only index hash changes are backend `.gitattributes` and Card `.github/workflows/validate.yml`; working files show the same exceptions, allowing only the previously approved LF/CRLF equivalence. All original production, tests, dependency files and acceptance-plan inputs remain unchanged. New tracked paths are exactly the declared acceptance documentation and review/evidence packaging paths; neither repository has untracked files.

- Card workflow: actual diff is solely `runs-on: ubuntu-latest` to `runs-on: ubuntu-24.04`. Verified by replacing that exact token in the previous blob and comparing the whole normalized workflow. The installed Python Playwright driver's `lib/server/registry/nativeDeps.js` explicitly contains `ubuntu24.04-x64`. This removes the unsupported Ubuntu 26.04 platform selection implicated in the parent-provided failed hosted run, without weakening tests or changing dependencies. Requirement remains the unchanged `playwright==1.56.0`; no assumption that the driver's embedded package version equals the Python distribution version is needed.
- Backend: appended rule is exactly `docs/reviews/approved-candidate-manifest.json -text whitespace=cr-at-eol`. Both working-tree and cached attribute queries show `text: unset`; cached whitespace is `cr-at-eol`. The inherited `eol: lf` does not re-enable conversion when text is unset. Git clean-filter hashing matches the staged blob.
- Original reviewer manifest, working packaged manifest and staged packaged manifest all have SHA-256 `15cb7ffb7e42705ec7617017df767e59f6df22b4a070d2daa71ea26b45dbc5cf`, and compare byte-for-byte equal. The existing HEAD copy differs only by CRLF-to-LF conversion. Thus the staged manifest repair restores the original approved evidence rather than modifying its content.
- Both P1 acceptance documents preserve shadow-only/no irrigation permission, deferred P2–P5, native scheduled-save versus crash-durability limits, and exact-head hosted CI as a separate gate. Their historical local-test table is not a claim that the successor workflow has executed.

## 2. Quality/security

Inspected the complete workflow and bounded attribute change after establishing SPEC equivalence. The workflow remains read-only (`contents: read`), timeout-bounded, with unchanged fixed commands/runtimes/artifact path. No Actions expression interpolation, secrets, release/deploy step, permissions expansion or new network destination is introduced. The file-specific attribute exception neither globally disables whitespace checks nor changes production normalization. No credential/privacy policy, runtime mutation path, HA access or actuator behavior changes.

Both repositories pass `git diff HEAD --check`. Original production/test/dependency hashes are preserved, so previous integrated quality conclusions remain applicable; full suites were intentionally not replayed. No blocking findings.

## Limits and artifacts

Approval is for these metadata fixes and publication equivalence, not a successful hosted CI claim, release or deployment authorization. The successor exact-head hosted checks must still pass after the parent pushes. No HA contact, source edits, staging, commits, GitHub writes or publication by this reviewer.

Created only this scratch report. One initial local dependency lookup incorrectly assumed a Node node_modules installation and exited after successful manifest/workflow verification; recovered using the actual Python `.venv/Lib/site-packages/playwright/driver/package/` path. No product issue resulted.
