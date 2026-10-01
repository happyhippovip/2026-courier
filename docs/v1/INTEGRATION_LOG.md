# Courier v1 — Integration Log

Owner: **L1 — Integration Owner / CI / Golden Harness**. L1 is the only lane that
merges into `integration/v1`. Every integration step is recorded here; an entry
is the evidence for that step, not a summary of intent.

## How a step is recorded and gated

- **Fields per step:** source branch, source SHA, resulting integration SHA,
  conflicts, manual resolution, targeted tests, overall test count, known
  remaining failures.
- **Resulting integration SHA** is the merge (or cherry-pick) commit that the
  tests ran on. The log commit that follows touches only this file and
  `.github/ci/known_failures.json`.
- **Overall test count** is `python -m pytest -q -p outcomes_plugin --timeout=180 --continue-on-collection-errors tests`.
  It runs on Python 3.12 with pinned dependencies (`pip install -e ".[test]"`) and
  ephemeral, distinct `COURIER_API_KEY` / `COURIER_VERIFIER_API_KEY`:
  - locally in the L1 container (Linux);
  - in CI through `.github/workflows/v1-ci.yml` (`ubuntu-latest`, `windows-latest`).
- **Gate:** `.github/ci/check_regressions.py` against
  `.github/ci/known_failures.json`. A step may not add a failure that is not
  in the previous step's baseline.
  - Known failures are removed when they are fixed, never added to hide a regression.
  - Tests are never disabled, skipped or xfailed to pass the gate.
- **Merge stops:** a lane is not merged if
  - its owned tests are red;
  - it touches another lane without explicit integration resolution;
  - it adds runtime state to git;
  - it bypasses the ledger contract.
- `integration/v1` only fast-forwards to a `lane/L1-integration` commit whose
  CI run is green on both platforms. No force pushes. `main` is never reset or
  rewritten.

## Pre-step — `main` drift (outside `integration/v1`)

- **Drift:** `origin/main` keeps receiving "Auto-reconcile Courier State" bot
  commits of `server/state/central_state.json` from
  `.github/workflows/courier_motor.yml`. The most recent is `980a7130`
  (2026-10-01 02:08 UTC), which landed after the fix below was opened.
- **Fix:** [happyhippovip/2026-courier#57](https://github.com/happyhippovip/2026-courier/pull/57)
  (branch `lane/L1-main-disable-autoreconcile`, `99cfb119`). It removes the
  5-minute schedule and the commit/push block, and sets `contents: read`.
  Open and mergeable. Merging is Dennis' decision.
- **Release path:** the eventual `integration/v1 → main` release is a
  merge-commit PR. It takes the integration `courier_motor.yml`, deletes
  `central_state.json` and keeps `main`'s three docs.

## Step 0 — v1 trunk and L1 foundation (2026-10-01)

| Field | Value |
|---|---|
| Source branch | trunk tip `e95aa787bdff0740bd8f925ce7462827a9bf999c` ("fix(mac-worker): add scripts/ to sys.path before resource_governor import") |
| Integration branch | `integration/v1` created at `e95aa787` (new branch; no force push) |
| L1 commits | `9e416f69` foundation (pyproject, pytest.ini marker, .gitignore, CI gate, golden harness, tests/legacy policy); `d0e690c9` CI continues on collection errors and uploads per-test outcomes |
| Resulting integration SHA | `d0e690c9e4a73006fe741dd9b723c47fef5cba8b` |
| Conflicts | none (L1-owned files only) |
| Manual resolution | none |
| Targeted tests | `tests/golden`: 11 collected, 11 skipped with the reason "golden harness waiting for v1 components: courier_core.serve, courier_core.journal, courier_core.projection, courier_worker.host, adapters.synthetic" |
| Overall, local Linux (Python 3.12.3) | 340 passed, 3 failed, 11 skipped; gate PASS |
| Overall, CI | [run 36805249973](https://github.com/happyhippovip/2026-courier/actions/runs/36805249973). **ubuntu-latest:** gate PASS, working tree clean. **windows-latest:** 256 passed, 48 failed, 12 skipped; baseline recorded from this run, working tree clean |

### Baseline measurement

The historical claim of 328 passed / 15 failed was **not reproduced**; the
environment it was measured in is unknown. With pinned dependencies:

- **Linux, local:**
  - 4 runs at `e95aa787`: 339–340 passed, 3–4 failed.
  - 13 runs to characterise flakiness.
- **Windows, CI:** one run at `d0e690c9`. All 48 failures have deterministic
  causes (below); further runs are gated against this baseline.

### Known remaining failures after step 0

**Linux (3 stable):**

| Test | Cause |
|---|---|
| `tests/test_failure_recovery_matrix.py::test_result_with_wrong_identity_is_rejected[dispatch_id]` | `server/app.py` answers 409 to any `dispatch_id` mismatch; the test expects 400 |
| `tests/test_p3_server_idempotency.py::test_failed_verification_can_be_resumed_with_new_attempt` | Same 409-vs-400 rule: a result of the superseded attempt 1 gets 409 instead of 400 |
| `tests/test_run_physical_restart.py::test_run_physical_restart_success` | The RUN 1 snapshot fixture lacks `candidate_sha`, and `scripts/run_physical_restart.py:86` refuses it as a stale bundle |

The first two are expected to be fixed by `muse/M07-adapter-evidence-confinement` (step 2).

**Linux, flaky (tolerated, still run):** all 9 tests in
`tests/test_muse_supervisor.py`. Across 13 local runs at `e95aa787`, 5
different tests failed intermittently, with timing-sensitive waits. The Muse
supervisor is frozen dev-swarm runtime and out of v1 scope.

**Windows (48, deterministic):**

| Cause | Affected tests |
|---|---|
| `scripts/mac_worker/runtime_state.py` imports POSIX-only `fcntl` | `test_mac_worker_contract` (10), `test_mac_worker_recovery` (9), `test_muse_supervisor` (9), `test_mac_worker_standalone_boot` (1), `test_muse_convergence` (collection) |
| `subprocess` `bash` resolves to the WSL launcher (no distribution installed) on the runner | `test_script_credentials` (11), `test_ci_acceptance_credentials` (2), `test_mac_worker_install` (1) |
| `os.setpgrp` does not exist on Windows | `test_run_physical::test_run_physical_success` |
| Same as Linux | the two 409-vs-400 tests and `run_physical_restart` |

These are portability defects of pre-v1 Mac/POSIX code, not regressions.
They are tracked here because Windows 11 is the primary v1 platform. The v1
worker host (L3) must not inherit them.

### Findings for owners (not fixed by L1)

- **Test isolation (owners of the legacy server/runtime tests):** the suite
  writes into the working tree.
  - `tests/test_run_physical.py` creates `courier_canary_process_a.txt` and
    `courier_canary_process_b.txt` at the repo root (verified in isolation).
  - Some test not yet identified writes `server/state/artifacts/records/*.json`
    through the default `ArtifactStore.from_env()` root used by `server/app.py`.

  Both paths are now ignored, and CI fails if a test writes any other
  non-ignored file. The tests should use `tmp_path`.
