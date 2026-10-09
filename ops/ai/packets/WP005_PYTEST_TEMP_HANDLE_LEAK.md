# WP005: Pytest subprocess orphans (Muse supervisor tests)

## Target
`scripts/mac_worker/runtime_state.py`
`scripts/mac_worker/muse_supervisor.py`
`scripts/mac_worker/supervisor_test_reaper.py`
`tests/test_muse_supervisor.py`
`tests/test_muse_supervisor_test_reaper.py`

## Incident record (2026-10-07)

| Field | Detail |
|---|---|
| **CAUSE** | Slot `process_identity` was captured only via `ps` (2s timeout). Under host pressure `ps` timed out → `None` identity persisted in slot state. |
| **TRIGGER** | Muse supervisor integration tests on a loaded CI/host; repeated slot restarts; `stop --terminate` could not prove ownership without identity. |
| **IMPACT** | Child bash/daemon trees survived ~12h; pytest temp dirs were deleted while processes still held handles / cwd; duplicate expensive CI runs (tracked separately as **#176**, out of L3 code scope). |
| **FIX** | `capture_process_identity(Popen)` at spawn (pgid via `os.getpgid`, Linux `/proc` fingerprint); `ps` is optional enrichment only. `SupervisorTestReaper` registers every test spawn and raises `CLEANUP_NOT_PROVEN` if termination cannot be proved. Bounded cleanup rounds (no infinite retry under pressure). |
| **REGRESSION TESTS** | `tests/test_muse_supervisor_test_reaper.py` (ps timeout, normal/forced kill, exception path, dead proc, fail-closed missing identity, unrelated process survival, stale-slot live detection, bounded retries). Muse supervisor tests wired through reaper fixture teardown. |
| **INVARIANT** | Tests and workers that spawn processes own their lifecycle; identity must not depend solely on later `ps`; cleanup succeeds only when termination is verified; unknown ownership fails closed (never kill by name). |

## Agent rule (spawned processes)

When adding or changing tests/tools that `Popen` a long-lived child:

1. Capture identity at spawn (`capture_process_identity` or `OwnedProcess.capture`).
2. Register with `SupervisorTestReaper` (tests) or journal ownership (production).
3. Teardown must call proven cleanup (`cleanup_group` / reaper) on success, failure, timeout, and Ctrl-C paths.
4. If cleanup cannot be proved, surface `CLEANUP_NOT_PROVEN` — do not delete temp dirs or claim success.
5. Do not ask a human to kill routine test-owned processes when ownership is provable.

## Defect (original Windows note)

When running `pytest` on Windows (`MUSE_WINDOWS`), the test session can crash during teardown with `PermissionError: [WinError 5]` on `pytest-current` if subprocesses leak handles on temp dirs. The Muse supervisor reaper and spawn-time identity above address the POSIX/mac_worker path; Windows package tests must still `terminate` + `wait` in fixtures.

## Causal Path

POSIX tests import `mac_worker` supervisors that spawn detached session leaders. Without spawn-time identity and verified teardown, orphaned groups outlive the pytest temp directory and break CI hygiene.
