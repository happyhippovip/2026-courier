# Windows automation checkpoint 080

Recorded for branch `cursor/windows-lock-import-be3a` after CUR-WIN-031 through CUR-WIN-080. Times below are Europe/Berlin.

## Branches and HEADs

| Branch | HEAD | Base | PR |
| --- | --- | --- | --- |
| `cursor/windows-lock-import-be3a` | behavior `29d5eb2b93572bae74724c9fee2857c7756977bb`; this file is the tip commit after it | `integration/v1` `d5b19f1df` | [#829](https://github.com/happyhippovip/2026-courier/pull/829) |
| `cursor/windows-installer-rc-be3a` | `9eef04817d98d1f761a81e7c8d9adb27d93089c3` | `integration/v1` | [#828](https://github.com/happyhippovip/2026-courier/pull/828) |

Push of `29d5eb2b9` to `origin/cursor/windows-lock-import-be3a` completed. No merge. No force-push.

## Exit codes

`scripts/windows_worker/daemon.py` `main()`:

| Code | Meaning |
| --- | --- |
| 0 | A live second instance already holds the file lock. No lease is taken. |
| 1 | Any other unexpected start error. |
| 2 | `COURIER_API_KEY` is missing. No network call. |
| 3 | Canonical lease missing, unreadable, stale, or refused. |
| 4 | `COURIER_SERVER` is missing. No private LAN address is used. |

A file lock without a canonical lease is exit 3. It is not exit 0.

## Tests run on this host

Python 3.12, pytest 9.1.1. No provider calls.

- `tests/test_artifact_upload_flow.py`, `tests/test_windows_resource_probe.py`, `tests/test_windows_lock_fail_closed.py`, `tests/test_windows_worker_contract.py`, `tests/test_windows_worker_recovery.py`, `tests/test_windows_local_queue.py`: 75 passed in 6.23s.
- `tests/test_work_queue.py` and `tests/test_work_queue_windows_lock.py` were included in an earlier run with the local queue file: 25 passed in 0.80s.

These are Linux process tests with local files. They are not a Windows installation test.

## CI

- PR #828 at `9eef04817`: Courier v1 CI run `39925994076` completed success, including `windows build`. That job does not compile Inno Setup. Customer-reality run `39925994221` completed success. Recorded 10:38–10:52 Europe/Berlin on 23 Oct 2026.
- PR #829 at `93be116c2`: Courier v1 CI run `39931810700` failed. Ubuntu and Windows pytest raised `CanonicalLeaseLost` in the upload and contract loops, and Windows raised `AttributeError: os.geteuid`. Commit `29d5eb2b9` is the fix.
- PR #829 tip `3b3b3c860`, Courier v1 CI run `39934137170`: Ubuntu pytest succeeded. Windows pytest failed while replacing `authority.db` (`WinError 32`, file still open in-process). That is a test restart, not a second writer. The following commit closes the store before the simulated restart. Windows build on that run was still going when the fix was committed. Customer-reality run `39934137018` succeeded at 11:45 Europe/Berlin and is not the pytest suite.

## Files changed on the lock branch

- `scripts/windows_worker/daemon.py`
- `scripts/windows_worker/local_queue.py`
- `tests/test_artifact_upload_flow.py`
- `tests/test_windows_local_queue.py`
- `tests/test_windows_lock_fail_closed.py`
- `tests/test_windows_resource_probe.py`
- `tests/test_windows_worker_contract.py`
- `tests/test_windows_worker_recovery.py`
- this checkpoint

## Commits on the lock branch

- `4cd9c28e6` missing lock module is a failed start
- `3ccde9bf1` CUR-WIN-031 refuse to run without a canonical lease
- `ad69eca73` CUR-WIN-031 loop does not exit clean without a lease
- `93be116c2` CUR-WIN-034..038 fail closed on lease loss
- `de8d04a32` CUR-WIN-040 recovery loops keep the real writer lease
- `8623c2cd3` CUR-WIN-039..050 stable exit codes and crash recovery
- `6e1be09af` CUR-WIN-051..060 local queue releases one verified workkey
- `29d5eb2b9` CUR-WIN-069 start the loop only with a canonical lease
- `c916cf2da` CUR-WIN-084 refuse to start without a server URL
- `a0bafa1cf` CUR-WIN-081 close the lease database before a simulated restart

## Lease

There is no separate git lease object. This branch is the only open writer for `scripts/windows_worker/daemon.py` and `scripts/windows_worker/local_queue.py`. PR #828 owns the Inno files and was not edited here. `courier_runtime/lease.py`, `scripts/windows_worker/build_package.ps1`, and the A→B provider path were not edited.

The daemon takes scope `worker:{id}`, workkey `daemon_loop`, and drops the file lock when that lease is missing. A live holder is not stolen. A dead local holder can be replaced. The local queue claims only as its own holder and does not release a `BLOCKED` dependency.

## Installer evidence

From PR #828 at `9eef04817`, not rebuilt here:

- `courier_installer.iss` SHA256 `4f7986a789cdfc1678b064d9c6f23d3f5758825231f01bf5d6080ba3c8a3f876`
- `build_installer.ps1` SHA256 `92024ffda3e47abdeebc065c97d2c348f5f6209fb4b3f8d9f1da50ddc25aea98`
- `CourierSetup-v1.exe`: absent. SHA256 UNPROVEN.
- `iscc`: absent on this host. Not downloaded.
- Silent install, uninstall, rollback, Start Menu session, and clean-machine acceptance: UNPROVEN.
- Self-hosted runner list: HTTP 403. No authorized host with Inno Setup 6 was found.
- Private checkpoint repository: HTTP 404 for this account. Not read. Not copied.

## Automation status

The daemon can keep running only while its canonical lease checks succeed. Lease loss exits 3 and is not retried. Heartbeat writes `health.json` with `verified: false` and does not release work. A `KILL` file stops the local queue before the next claim. Backoff is capped at 300 seconds.

Not activated in this session: Windows service install, Task Scheduler, logon autostart, a Cursor cloud agent, or any paid runner. GitHub Actions on the existing pull-request workflows is the only resume path, and it runs only when a push or PR event arrives. No process was left running after these tests.

## #827 union on this branch

Checked 23 Oct 2026, Europe/Berlin. HEADs before this commit: #827 `e678b36e3`, #829 `1bcaf9299`, union basis `5bc42fbbe`. A merge of those two heads conflicts only in `scripts/windows_worker/daemon.py` and `tests/test_windows_lock_fail_closed.py`.

This commit keeps both behaviors. #829 still refuses to start when the LeaseStore is missing, stale, or held by a live writer. #827's symlink refusal, lock-path checks, and the Windows lock offset stay. `get_authority_store()` returning `None` raises `CanonicalLeaseLost` and is not a successful lock. The bridge cost gate on #827 was not edited.

Red before the test change: `acquire_lock` with `get_authority_store` stubbed to `None` raised `CanonicalLeaseLost` (`NoneType` has no `acquire`) where the old #827 test expected a lock path. Green after, on this tree: 71 passed in `test_windows_lock_fail_closed.py`, `test_windows_appdata_symlink.py`, `test_windows_daemon_token.py`, `test_windows_worker_recovery.py`, `test_windows_local_queue.py`, `test_windows_costgate_and_writer_lease.py`, and `test_windows_worker_contract.py`.

## Next queue

Deduplicated from what is still open. Do not restart 031–080.

1. CUR-WIN-085 — Read CI for the push that contains `c916cf2da` and `a0bafa1cf`. Fix only failures in files this branch owns.
2. CUR-WIN-082 — On an authorized Windows host that already has Inno Setup 6, build `CourierSetup-v1.exe` and record its real SHA256. Until then this stays BLOCKED.
3. CUR-WIN-083 — Silent install, uninstall, rollback, and clean-machine acceptance on an explicitly authorized test machine.
