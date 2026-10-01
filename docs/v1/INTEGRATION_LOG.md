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

## Step 0b — Rule 0 and next-chat handoff (2026-10-01)

| Field | Value |
|---|---|
| Source branch | `lane/L1-product-rule-zero`, pushed from the owner account; Issue #54 asks L1 to merge it |
| Source SHA | `8df37cda32c15c24b5fb4c5ca5d9d9c03426cd78` (includes `dd207057`) |
| Resulting integration SHA | `8c04aa6f` (merge commit, `--no-ff`) |
| Files | `docs/V1_RULE_0.md`, `docs/NEXT_CHAT_HANDOFF.md` (documentation only) |
| Conflicts | none |
| Manual resolution | none |
| Targeted tests | none (no code) |
| Overall, local Linux | 339 passed, 4 failed, 11 skipped; gate PASS. The 4th failure is the known flaky `test_muse_supervisor.py::test_stop_prevents_restart` |
| Overall, CI | not triggered (docs-only push; `paths-ignore`). The code tree is identical to `90af2405`, which passed run 36805675912 |
| Known remaining failures | unchanged from step 0 |

## Step 1 — `m06/dispatcher-persist-oexcl` — BLOCKED, merge reverted (2026-10-01)

| Field | Value |
|---|---|
| Source branch | `m06/dispatcher-persist-oexcl` (4 commits on `e95aa787`: `0faea67e` M06-01, `52fbc9f7` M06-02, `737959ea` M06-03, `d8265a5b` M06-05) |
| Source SHA | `d8265a5b` |
| Merge commit | `8b58dd4b` (`--no-ff`); never reached `integration/v1` |
| Revert commit | `efe60061` (`git revert -m 1 8b58dd4b`); tree identical to `0413f830` |
| Resulting integration SHA | unchanged: `integration/v1` stays at `90af2405` |
| Conflicts | none |
| Manual resolution | none |
| Targeted tests, local Linux | `test_github_dispatcher_persist_race`, `test_github_worker_adapter_dispatch_crash`, `test_github_worker_adapter_packet_lock`, `test_github_worker_adapter_state_atomic`, `test_github_worker_adapter`: 28 passed |
| Overall, local Linux | 350 passed, 3 failed (known), 11 skipped; gate PASS |
| Overall, CI | [run 36806012206](https://github.com/happyhippovip/2026-courier/actions/runs/36806012206). **ubuntu-latest:** PASS. **windows-latest:** gate FAIL, 265 passed, 49 failed, 12 skipped |
| Known remaining failures | unchanged from step 0 |

**Why blocked.** The new Windows failure is in a test owned by the merged lane:
`tests/test_github_worker_adapter_state_atomic.py::test_concurrent_writes_never_tear_reads`.
It fails with `PermissionError(13, 'Permission denied')` ×2 and
`PermissionError(13, 'Access is denied')` ×2.

M06-05 publishes state via a thread-unique tmp file, fsync, then `os.replace`.
On Windows, `os.replace` cannot replace a file that another handle holds open
without `FILE_SHARE_DELETE`, which is how Python opens files. Readers can also
hit the file while it is being replaced. So the lane's own contract ("readers
only ever see complete state or nothing") does not hold on the primary v1
platform.

Under the merge rules (owned tests red; L1 does not write lane code; no
baseline entries added to hide a regression), the merge was reverted rather
than tolerated.

**Re-integration.**
1. The lane makes the publish/read path Windows-safe, for example bounded
   retry on `PermissionError` for both writer and reader, or a lock.
2. Its tests must pass on `windows-latest`.
3. L1 then runs `git revert efe60061` to re-apply the four M06 commits, merges
   the fixed branch, and re-resolves `scripts/github_worker_adapter.py` with M07.
   That combination was already rehearsed: it auto-merges, and both the atomic
   publish and the evidence confinement survive.

## Step 2 — `muse/M07-adapter-evidence-confinement` (2026-10-01)

| Field | Value |
|---|---|
| Source branch | `muse/M07-adapter-evidence-confinement` (7 commits on `ff79fbe4`, an ancestor of `e95aa787`: `76690253`, `4decc110`, `5bd5c774`, `e0b767b3`, `e05a3601`, `0993f592`, `b2dbfead`) |
| Source SHA | `b2dbfead` |
| Resulting integration SHA | `6c32d11d` (merge commit, `--no-ff`) |
| Files | `server/app.py`, `scripts/github_worker_adapter.py`, `tests/test_failure_recovery_matrix.py`, `tests/test_github_worker_adapter.py`, `tests/test_result_dispatch_binding.py` (new) |
| Conflicts | `server/app.py`, `task_result()` dispatch check, one hunk |
| Manual resolution | Took M07's line (see below). `scripts/github_worker_adapter.py` merged without conflict, because m06 is not in the trunk (step 1) |
| Targeted tests | `test_github_worker_adapter`, `test_result_dispatch_binding`, `test_failure_recovery_matrix`, `test_p3_server_idempotency`, `test_server_integration_contract`: 85 passed |
| Overall, local Linux | 356 passed, 1 failed (known), 11 skipped; gate PASS |
| Overall, CI | [run 36806672165](https://github.com/happyhippovip/2026-courier/actions/runs/36806672165). **ubuntu-latest:** PASS. **windows-latest:** PASS, 272 passed, 46 failed (known), 12 skipped. Both report NOW PASSING / MISSING for the two entries removed below |
| Baseline change | Removed on both platforms: `test_p3_server_idempotency.py::test_failed_verification_can_be_resumed_with_new_attempt` (now passes) and `test_failure_recovery_matrix.py::test_result_with_wrong_identity_is_rejected[dispatch_id]`. M07 (`0993f592`) re-parametrized the latter as `[dispatch_id-409]`, which passes |
| Known remaining failures | Linux: `test_run_physical_restart` + 9 flaky muse. Windows: 46 (the 48 of step 0 minus the two above) |

**Conflict and resolution.**

- Trunk (`3d566820`): `if task.get("dispatch_id") and data.get("dispatch_id") != task.get("dispatch_id"): 409`.
- M07: `if data.get("attempt_id") == task.get("attempt_id") and data.get("dispatch_id") and data.get("dispatch_id") != task.get("dispatch_id"): 409`.

Taking M07's line keeps 409 for a carried dispatch mismatch within the same
attempt (cross-dispatch replay). Missing or empty dispatch ids and results of
superseded attempts go back to 400 validation in
`scripts/integration_contract.validate_durable_result`, which rejects any
missing or mismatched goal/task/attempt/dispatch/worker id. So nothing that
trunk rejected is accepted now; only the status code differs, and the task
stays `DISPATCHED` in every case. This is the 409-vs-400 contract the plan
required to turn green.

**Open finding (owner lane L4, not fixed by L1).** The new evidence-path
confinement in `verify_result` rejects `..` and POSIX absolute paths. On
Windows, rooted driveless paths still escape the download directory
(`/etc/passwd` becomes `D:\etc\passwd`, `\Windows\win.ini` becomes
`D:\Windows\win.ini`), and so do drive-relative paths (`C:foo.txt`). This was
verified with `PureWindowsPath`. Suggested fix: reject any drive or root, and
check `resolve()` containment.

## Step 3 — `mac/M05-intake-dispatch-binding` (2026-10-01)

| Field | Value |
|---|---|
| Source branch | `mac/M05-intake-dispatch-binding` (4 commits on `e95aa787`: `0d04abd6` Q1, `fbc4accd` Q2, `3ac285b7` Q3, `8da27318` Q4) |
| Source SHA | `8da27318` |
| Resulting integration SHA | `dd933e29` (merge commit, `--no-ff`) |
| Files | `scripts/intake_dispatcher.py`, `scripts/queue_processor.py`, 4 new test modules |
| Conflicts | none |
| Manual resolution | none |
| Stop-condition check | No runtime state added to git. The tests `chdir` into `tmp_path`, so `central_state.json` is written there. `save_central_state` is tmp + fsync + `os.replace` of a cwd-relative legacy file, not a ledger write |
| Targeted tests | `test_intake_central_state`, `test_intake_dispatch_binding`, `test_intake_dispatch_marker`, `test_queue_redispatch_skip`: 20 passed |
| Overall, local Linux | 376 passed, 1 failed (known), 11 skipped; gate PASS |
| Overall, CI | [run 36806919861](https://github.com/happyhippovip/2026-courier/actions/runs/36806919861). **ubuntu-latest:** PASS. **windows-latest:** PASS, 292 passed, 46 failed (known), 12 skipped; working trees clean |
| Known remaining failures | unchanged from step 2 |

**Note.** M05's atomic `central_state.json` save uses `os.replace`, like
m06. Its tests are not concurrent and pass on Windows, but the same Windows
sharing-violation risk applies if readers hold the file open. This is legacy
snapshot state that v1 retires in favour of the SQLite journal (L2).

## Step 4 — `courier-ui/cobalt-nova/OVERLAY-REPLAY` — BLOCKED, not merged (2026-10-01)

| Field | Value |
|---|---|
| Source branch | `courier-ui/cobalt-nova/OVERLAY-REPLAY` (10 commits on `e95aa787`, `8b1e94db`..`a53b3c73`) |
| Source SHA | `a53b3c73` |
| Resulting integration SHA | unchanged (not merged) |
| Files | `courier_overlay/__init__.py`, `courier_overlay/event_bus.py`, `tests/test_desktop_event_bus.py` |
| Conflicts | none; it merges cleanly |
| Targeted tests, local Linux | `test_desktop_event_bus`: all pass |
| Evidence | Preflight [run 36806319325](https://github.com/happyhippovip/2026-courier/actions/runs/36806319325) on `lane/L1-preflight` (`c605ae55`, the planned steps 2–7 on `e29805b2`). **ubuntu-latest:** PASS. **windows-latest:** two new failures in this lane's own tests |

**Why blocked.**

- `test_desktop_event_bus.py::test_concurrent_appends_all_persisted` fails with
  `assert 4 == 8`. On Windows only 4 of 8 concurrently emitted events are read
  back. That is event loss in the append-only bus the Desktop Hub is meant to
  build on.
- `test_desktop_event_bus.py::test_emit_dir_fsync_failure_is_loud_but_persisted`
  fails with `DID NOT RAISE OSError`. The directory-fsync contract is not
  exercised on Windows.

Windows 11 is the primary v1 platform, the lane's owned tests are red there,
and L1 does not write lane code. Not merged. The fix goes to the owning lane
(L5).

## CI policy — platform scope for POSIX-only components (L1 decision, 2026-10-01)

**Decision.** On `windows-latest`, failures of tests matching
`tests/test_mac_*` are reported as OUT OF SCOPE and do not fail the gate.
The scope is recorded in `.github/ci/known_failures.json` →
`Windows.out_of_scope`.

- These tests still run on Windows and are listed in every report.
- On Linux they stay fully gated.
- Every other test is gated on both platforms exactly as before.

**Why.**

- `scripts/mac_worker` is the legacy macOS worker. It imports `fcntl` and
  uses POSIX process groups, so it cannot run on Windows by design.
- The Windows baseline already holds 21 `test_mac_*` failures with this root
  cause, recorded at step 0.
- The planned M2 hardening lanes (steps 5–6) add 19 more tests of the same
  component. In the preflight [run 36806319325](https://github.com/happyhippovip/2026-courier/actions/runs/36806319325)
  each of them fails on Windows only with `ModuleNotFoundError: No module named 'fcntl'`
  and passes on Linux.
- Treating "cannot import on Windows" as a regression would block valid Mac
  hardening forever without protecting any Windows behaviour.
- The v1 Windows worker host is L3's `courier_worker`, which the golden
  harness gates on both platforms.

**Limits.**

- The scope covers only `tests/test_mac_*`.
- Windows-relevant components found red on Windows stay blocked. This applies
  to m06 (step 1), OVERLAY (step 4) and the Windows worker timeout kill
  (step 7).

**Gate visibility.** The gate also emits a one-line `::notice` annotation per
platform: passed / failed / skipped / new / now_passing / out_of_scope.

**Reversal.** Delete `Windows.out_of_scope` from `known_failures.json`. The
Mac tests then count as Windows failures again. This changes no code.

## Step 5 — `M2/mac-agy-orphan-marker`, including G1 and the agy heartbeat (2026-10-01)

| Field | Value |
|---|---|
| Source branch | `M2/mac-agy-orphan-marker`; its ancestors `G1/mac-agy-kill-reap` (`adad9731`) and `M2/mac-agy-heartbeat` (`e26a98e3`) come with it. 4 commits on `e95aa787`: `c52a699c`, `adad9731`, `e26a98e3`, `9add426e` |
| Source SHA | `9add426e` |
| Resulting integration SHA | `57e994e3` (merge commit, `--no-ff`) |
| Files | `scripts/mac_worker/daemon.py`, `tests/test_mac_agy_timeout_reap.py`, `tests/test_mac_agy_heartbeat.py`, `tests/test_mac_agy_orphan_marker.py` |
| Conflicts | none |
| Manual resolution | none |
| Targeted tests | `test_mac_agy_timeout_reap`, `test_mac_agy_heartbeat`, `test_mac_agy_orphan_marker`, plus the existing `test_mac_worker_contract`, `test_mac_worker_recovery`, `test_mac_worker_standalone_boot`: 28 passed |
| Overall, local Linux | 384 passed, 1 failed (known), 11 skipped; gate PASS |
| Overall, CI | [run 36807288154](https://github.com/happyhippovip/2026-courier/actions/runs/36807288154). **ubuntu-latest:** PASS, 382 passed, 3 failed (1 known + 2 known-flaky muse), 11 skipped. **windows-latest:** PASS, 292 passed, 54 failed, 12 skipped; new=0, out_of_scope=8 (the 8 new agy tests, `fcntl`) |
| Known remaining failures | unchanged from step 2 (Linux 1 + 9 flaky; Windows 46 + scoped Mac tests) |

## Step 6 — `M2/mac-deliver-heartbeat`, the native stack (2026-10-01)

| Field | Value |
|---|---|
| Source branch | `M2/mac-deliver-heartbeat`; its ancestors `M2/mac-native-timeout-reap` (`60833112`), `M2/mac-native-heartbeat` (`56d29700`) and `M2/mac-native-orphan-marker` (`04b997ab`) come with it. 4 commits on `e95aa787` |
| Source SHA | `fb3d6a22` |
| Resulting integration SHA | `f66f9dba` (merge commit, `--no-ff`) |
| Files | `scripts/mac_worker/daemon.py`, `tests/test_mac_native_timeout_reap.py`, `tests/test_mac_native_heartbeat.py`, `tests/test_mac_native_orphan_marker.py`, `tests/test_mac_deliver_heartbeat.py` |
| Conflicts | `scripts/mac_worker/daemon.py`, 2 hunks against step 5 (agy) |
| Manual resolution | Done once, by hand, keeping both hardening sets (see below). Byte-identical to the preflight resolution `c605ae55` |
| Targeted tests | the 4 native/deliver modules plus the 3 agy modules and `test_mac_worker_contract`, `test_mac_worker_recovery`, `test_mac_worker_standalone_boot`: 39 passed |
| Overall, local Linux | 394 passed, 2 failed (1 known + flaky `test_muse_supervisor.py::test_result_ready_is_only_redelivered`), 11 skipped; gate PASS |
| Overall, CI | [run 36807606574](https://github.com/happyhippovip/2026-courier/actions/runs/36807606574). **ubuntu-latest:** PASS, 395 passed, 1 failed (known), 11 skipped. **windows-latest:** PASS, 292 passed, 65 failed, 12 skipped; new=0, out_of_scope=19 (all new agy and native Mac tests, `fcntl`) |
| Known remaining failures | Linux: `test_run_physical_restart` + 9 flaky muse. Windows: 46 + scoped Mac tests |

**Resolution of `scripts/mac_worker/daemon.py`.**

1. **Heartbeat constants:** kept both `AGY_HEARTBEAT_INTERVAL_SECONDS = 30`
   and `NATIVE_HEARTBEAT_INTERVAL_SECONDS = 30`, with their comments.
2. **`require_no_orphan()`:** the restart gate now checks all three execution
   markers: `muse_process.json`, `agy_process.json` and
   `native_process.json`. The native branch's own comment anticipated this:
   "the agy marker joins this gate on the agy line; merge composes them".
3. **Auto-merged region:** run_native's new `finally` reap (fail closed when
   cleanup is unproven) and agy's `_reap_agy_group` helper sit side by side.
   PEP 8 spacing between them was restored.

`runtime_state.same_process` is imported but unused. That is already true on
the trunk and on both branches; it was not introduced by this merge.

## Step 7 — cherry-pick `724aee46` from `google/windows-worker-timeout-kill` — BLOCKED, not applied (2026-10-01)

| Field | Value |
|---|---|
| Source | commit `724aee46` ("fix(windows-worker): kill timed-out PowerShell child instead of leaving it running"), cherry-pick only; the branch's base lineage (`dd3d2644` …) is not merged |
| Resulting integration SHA | unchanged (not applied) |
| Files | `scripts/windows_worker/daemon.py`, `tests/test_windows_worker_timeout_kill.py` |
| Conflicts | none; it applies cleanly onto the current trunk version of the daemon |
| Targeted tests, local Linux | `test_windows_worker_timeout_kill`: 2 passed |
| Evidence | Preflight [run 36806319325](https://github.com/happyhippovip/2026-courier/actions/runs/36806319325). **windows-latest:** `test_windows_worker_timeout_kill.py::test_timed_out_process_is_killed_not_left_running` fails with "child process from the timed-out task is still running (orphaned)". The runner's cleanup also reports `Terminate orphan process: ... (sleep)` |

**Why blocked.** The test replaces `daemon.subprocess.Popen`, which is the
global `subprocess.Popen`. So `kill_process_tree()`'s
`subprocess.run(["taskkill", ...])` also spawns `sleep 30` instead of
`taskkill`, and the call times out under the patched `communicate`. The
liveness probe `os.kill(pid, 0)` also sends `CTRL_C_EVENT` on Windows instead
of probing the process.

The commit message itself says the test only exercises the non-Windows path.
On the only platform this worker targets, the fix is unproven and the lane's
test leaves an orphan. Not applied. The fix goes to the owning lane (L3).

## Merge plan status (2026-10-01, end of L1 cycle 1)

| Step | Source (SHA) | Result | Integration SHA |
|---|---|---|---|
| 0 | trunk `e95aa787` + L1 foundation | merged | `9e416f69`, `d0e690c9` (+ log `90af2405`) |
| 0b | `lane/L1-product-rule-zero` (`8df37cda`) | merged (docs) | `8c04aa6f` |
| 1 | `m06/dispatcher-persist-oexcl` (`d8265a5b`) | **BLOCKED**: Windows; merge `8b58dd4b` reverted by `efe60061` | — |
| 2 | `muse/M07-adapter-evidence-confinement` (`b2dbfead`) | merged; 409-vs-400 green | `6c32d11d` |
| 3 | `mac/M05-intake-dispatch-binding` (`8da27318`) | merged | `dd933e29` |
| 4 | `courier-ui/cobalt-nova/OVERLAY-REPLAY` (`a53b3c73`) | **BLOCKED**: Windows event loss; not merged | — |
| — | CI policy: Windows scope for `tests/test_mac_*` | applied | `7b596685` |
| 5 | `M2/mac-agy-orphan-marker` (`9add426e`), with G1 and agy heartbeat | merged | `57e994e3` |
| 6 | `M2/mac-deliver-heartbeat` (`fb3d6a22`), native stack | merged; `daemon.py` resolved by hand | `f66f9dba` |
| 7 | cherry-pick `724aee46` (Windows timeout kill) | **BLOCKED**: Windows test invalid, orphan left; not applied | — |

**Gate at `f66f9dba`.**

- Linux: 395 passed, 1 known failure (`test_run_physical_restart`), 9 tolerated flaky muse tests.
- Windows: 292 passed, 46 known failures, Mac tests out of scope, 0 new.
- Golden harness: 11 tests, all skipped until `courier_core` / `courier_worker` / `adapters.synthetic` exist.

**Re-integration of blocked lanes.**

- Each lane fixes its Windows defect on a `lane/**` branch, where `v1-ci.yml`
  runs both platforms.
- L1 then merges it as a new step. For m06, L1 first runs `git revert efe60061`.

**Preflight.** Before merging a batch, L1 pushes the planned end state to
`lane/L1-preflight` (L1-owned, never merged). One Windows CI run then shows
every Windows blocker in advance.

## Step 8 — runtime state out of git; root scratch to `attic/` (L1 cycle 2, 2026-10-01)

| Field | Value |
|---|---|
| Source | L1-owned change on `lane/L1-integration` (no lane merge) |
| Base | `c2a10c6b`, which is `integration/v1` as re-verified at the start of cycle 2 |
| Resulting integration SHA | `66996a59` |
| Conflicts | none |
| Untracked (`git rm --cached`; history keeps them; now ignored) | 40 files: `server/state/central_state.json`, `server/state/artifacts/records/*` (24) and `blobs/*` (2), `logs/courier_daemon.{log,pid}`, `runtime/resource_guard/{heavy.lock,heavy_jobs.sqlite3}`, `runtime/harmless_staging_marker.json`, `scripts/mac_worker/logs/*.log` (3), `scripts/windows_worker/courier_canary_test-win-001.txt`, `work_dir/report.{json,md}`, root `central_state.json`, root `courier_canary_*.txt` (2) |
| Moved to `attic/root-scratch-2026-10-01/` (`git mv`) | 17 root files. Smoke scripts: `test_canary.py`, `test_retry.py`, `phase8_workforce_temp.py`. Sample tasks: `dummy_task*.json`, `task.json`, `test_mac_task.json`. Root outputs: `result.json`, `gemini_result*.json` (3), `handoff.json`, `reconciliation.json`, `founder_concierge_result.json`, `agy_test_{out,err}.txt` |
| Kept | `logs/.gitkeep` (`scripts/start_daemon.sh` redirects into `logs/`), `runtime/content/.gitkeep`. Every docs/, tasks/, fixtures/ and events/ file is untouched |
| Targeted check | Full suite on a **fresh checkout** of `66996a59`, without any of the untracked files: 394 passed, 2 failed (known `run_physical_restart` + known-flaky `test_four_slots_are_isolated`), 11 skipped; gate PASS. Working tree clean after the run |
| Overall, CI | [run 36810546224](https://github.com/happyhippovip/2026-courier/actions/runs/36810546224). **ubuntu-latest:** PASS, 395 passed, 1 failed (known), 11 skipped. **windows-latest:** PASS, 292 passed, 65 failed (46 known + 19 Mac tests out of scope), 12 skipped, new=0. Both "working tree clean" checks pass |
| Known remaining failures | unchanged |

**Why this is safe.**

- `server/app.py` treats a missing state file as empty state.
- `ArtifactStore` creates its `records/` and `blobs/` directories, and the
  Mac daemon creates its state and log directories.
- No code, test or workflow reads any moved file. The scripts and workflows
  that mention these names only *write* same-named outputs: the revenue
  workflow writes `task.json`/`result.json`/`handoff.json`/`reconciliation.json`,
  `gemini_worker_adapter` writes `dummy_task_{2,3}.json`, the founder demo writes
  `founder_concierge_result.json`, and `intake_dispatcher`/`queue_processor`
  write a cwd-relative `central_state.json`. Those names are now ignored at
  the root, so the writers no longer dirty the tree.

**Not changed.** `main` still tracks `server/state/central_state.json`, and its
motor workflow still commits it until PR #57 is merged. The eventual
`integration/v1 → main` release removes it.

**Lane watch (cycle 2 start).** No corrected source has been pushed for the
three blocked lanes:

- `m06/dispatcher-persist-oexcl` is still `d8265a5b`.
- `courier-ui/cobalt-nova/OVERLAY-REPLAY` is still `a53b3c73`.
- `google/windows-worker-timeout-kill` is still `724aee46`.

They stay out of `integration/v1`.

### Step 8 addendum — intermittent Windows failure on the step-8 log head

- **Run:** [run 36810693808](https://github.com/happyhippovip/2026-courier/actions/runs/36810693808),
  a `workflow_dispatch` run on `348f6cbb`, a docs-only commit whose code is
  identical to the green `66996a59`.
- **Attempt 1:** `windows-latest` reported one new failure:
  `tests/test_resource_policy_mission_093.py::TestMission093And095And097HardenedPolicy::test_03b_atomic_expired_lease_reclaim_single_winner`.
- **Attempt 2 (single re-run):** PASS, 292 passed, 65 failed (known and out of scope), 12 skipped, new=0.
- **History:** the same test passed in about 10 earlier Windows runs. Neither
  the test nor `TaskLeaseManager` has changed since `e95aa787`. This is not a
  regression from any integration step.

The test races two processes to reclaim an expired lease and requires exactly
one winner. An intermittent failure therefore points to a real Windows race
in the reclaim path. The failure was only seen in the log summary; the
detailed assertion was not retrievable.

**Action.** The test is recorded as Windows flaky in `known_failures.json`
(`Windows.flaky`, with `flaky_note`). It still runs, and every failure is
listed. The race is a finding for its owner (resource-policy / lease code).
L1 does not change that code. `integration/v1` was not advanced on the red
attempt.

## Step 9 — `lane/L2-journal`, the v1 core journal (L1 cycle 3, 2026-10-01)

| Field | Value |
|---|---|
| Source branch | `lane/L2-journal` (1 commit on `c2a10c6b`) |
| Source SHA | `48cf54f5` |
| Resulting integration SHA | `d1f61f1a` (merge commit, `--no-ff`, onto `655cb94b`) |
| Files | new only: `courier_core/{__init__,events,state_machine,journal,projection}.py`, `tests/core/{core_builders,test_core_events,test_core_state_machine,test_core_journal,test_core_projection}.py` |
| Conflicts | none |
| Manual resolution | none |
| Stop-condition check | Lane CI [run 36809684753](https://github.com/happyhippovip/2026-courier/actions/runs/36809684753) green on both platforms. Touches no other lane's paths. Adds no runtime state (the tests write only to `tmp_path`; CI tree-clean checks pass). Implements the ledger contract rather than bypassing it: the events table, `Journal(path).open()`, `.verify_chain().ok`, `projection_hash(conn)` and `rebuild(journal, out_path)` match `tests/golden/README.md` |
| Targeted tests | `tests/core`: 65 passed |
| Golden harness | still 11 skipped. It now waits only for `courier_core.serve`, `courier_worker.host` and `adapters.synthetic`; `courier_core.journal` and `courier_core.projection` are found |
| Overall, local Linux | 459 passed, 2 failed (known + known-flaky `test_result_ready_is_only_redelivered`), 11 skipped; gate PASS |
| Overall, CI | [run 36811357331](https://github.com/happyhippovip/2026-courier/actions/runs/36811357331). **ubuntu-latest:** PASS, 459 / 2 / 11. **windows-latest:** PASS, 357 passed (292 + 65 core), 65 failed (known + 19 out of scope), 12 skipped, new=0 |
| Known remaining failures | unchanged |

**Lane watch.** m06 (`d8265a5b`), OVERLAY (`a53b3c73`) and g05 (`724aee46`)
are unchanged and still blocked. PR #57 is unchanged: open, mergeable, and
waiting on Dennis.
