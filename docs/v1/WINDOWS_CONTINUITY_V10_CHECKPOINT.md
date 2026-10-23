# Windows continuity V10

Recorded 23 Oct 2026, Europe/Berlin, on `cursor/windows-lock-import-be3a`. No merge. No service. No Task Scheduler entry. No provider call.

| Key | Result |
| --- | --- |
| WIN-CONT-001 | #829 `c95477941` and #828 `95463249f` are both `MERGEABLE` / `CLEAN` against `integration/v1` `d5b19f1df`. Every listed check on both PRs is SUCCESS. #827 moved to `3fe68c149` and is `UNSTABLE` on base `cursor/ab-master-9ba8`. |
| WIN-CONT-002 | Run [39951521039](https://github.com/happyhippovip/2026-courier/actions/runs/39951521039), job `120406866483`, re-read this session. `CourierSetup-v1.exe` SHA256 `C424171C842550E620BC98908FB9E9D71B4D2DB3D63D46530A757D425A1DE828`, built from merge `780e247992555eb67a3a40b32d493454c54b008e`. Log lines: `CLEAN MACHINE`, silent install, Start menu shortcut, silent upgrade, silent uninstall. Inno Setup 6 already on the runner. Not rebuilt here. |
| WIN-CONT-003 | Merging #827 `3fe68c149` into #829 `c95477941` still conflicts only in `scripts/windows_worker/daemon.py` and `tests/test_windows_lock_fail_closed.py`. The new #827 commit does not touch those files. Keep this branch's copies. The merge was not committed. |
| WIN-CONT-004 | A dead pid on another host no longer clears the local lease. Same-machine dead pid still can. |
| WIN-CONT-005 | Two homes, one queue, workkey `WQ-1`: the second home does not run it. |
| WIN-CONT-006 | `run_task` sees `STARTED` on disk. A file that is still `CLAIMED` is not the execution window. |
| WIN-CONT-007 | A rejected result is `RELEASE_PENDING` on disk before the worker is freed. Restart does not run it again. |
| WIN-CONT-008 | A dead letter is not executed again and is not released. A second identical `BLOCKED` release is idempotent. |
| WIN-CONT-009 | A `KILL` file stops the next retry inside `run_once`. The claim stays claimed. |
| WIN-CONT-010 | L1 handoff: `docs/v1/WINDOWS_L1_RELEASE_HANDOFF.md`. |

Focused Linux pytest after the code change: 63 passed in `test_windows_lock_fail_closed.py`, `test_windows_local_queue.py`, `test_windows_worker_recovery.py`, `test_windows_worker_contract.py`, `test_windows_resource_probe.py`. That run is not the Windows CI result.
