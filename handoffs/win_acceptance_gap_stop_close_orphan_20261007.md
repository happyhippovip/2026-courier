# WIN Acceptance GAP 1 — user-facing stop/close path (Rule 0 step 7)

Date: 2026-10-07. Worker: Windows clean-machine acceptance (shell-less session).
HEAD verified: `integration/v1` = `b9fc486a` (2026-10-07T17:41:13Z).
All file facts below observed via raw read at that HEAD, not inferred.

## Chain legs

close -> no orphan process (Rule 0 step 7, Quality Bar S4.1/S5).

## Finding (observed)

1. `scripts/windows_worker/stop.bat` (97 bytes) is the shipped user-facing stop:
   `taskkill /F /IM Courier.exe`, then unconditional `echo Stopped.`
   - System-wide name-based kill: hits ANY process named Courier.exe
     (other user, CI runner, second checkout). No ownership check.
   - No verification: prints `Stopped.` even when nothing was killed.
   - No graceful path: never uses the launcher's Ctrl handler /
     `POST /v1/shutdown` (exists in `CourierLauncher.cs`, Step 19).
   - Contradicts `docs/V1_PRODUCT_QUALITY_BAR.md` S4.1/S5 and the Step-10
     review ("rules out broad taskkill as the final containment").
2. `scripts/windows_worker/install.ps1` copies `$PSScriptRoot\*` to
   `%ProgramFiles%\CourierWorker`, so `stop.bat` SHIPS to users.
3. `scripts/windows_worker/uninstall.ps1` stops only the `CourierWindowsWorker`
   scheduled task. An interactively launched `Courier.exe` (via `start.bat`
   or double-click) keeps running while program files are deleted under it.
   No orphan/process check before or after removal.
4. The harness (`tests/test_win_clean_machine_harness.py`) kills the launcher
   by owned PID (`taskkill /T /F /PID`), so none of the above is exercised
   by any test. PR #157 adds orphan assertions to that file but does not
   touch these scripts.

## Why this scope is free

Open PRs at check time: exactly #132-#159 (28, pages 1-2; page 3 empty).
- #133 (Grok): build_package.ps1 + CourierLauncher.cs health wait +
  contract test + smoke workflow. Untouched: stop/start/install/uninstall.
- #135 (Grok): courier_doctor.py redaction only.
- #157 (L1): only `tests/test_win_clean_machine_harness.py` (single-file diff).
- No other open PR title/body covers stop.bat, start.bat, install.ps1,
  uninstall.ps1.
No edit to `CourierLauncher.cs` is proposed here (Grok file, #133).

## Live-evidence status

BLOCKED in this session: shell sandbox setup fails
(`admit deny-read ... deny_read_acl_state.json`), so no local execution.
NOT claimed as proven. Runbook below produces the evidence on a
shell-capable Windows host.

## Runbook (shell-capable Windows host, repo at integration/v1)

Setup: build `Courier.exe` per `launcher/build_launcher.ps1`, set
`COURIER_HOME=%TEMP%\CourierGap1`, start one interactive instance,
note `$launcherPid`. Start a DECOY `Courier.exe` copy under a different
name? No — exact test needs a second same-name process: copy the exe
to `%TEMP%\decoy\Courier.exe`, start it with `COURIER_HOME=%TEMP%\decoyHome`
(note `$decoyPid`), wait for its token file.

1. Run `scripts\windows_worker\stop.bat`.
2. Record: exit code, stdout, `$launcherPid` alive?, `$decoyPid` alive?,
   worker/controller/hub children alive? (`Get-CimInstance Win32_Process`
   filtered by parent chain, plus `courier.db` journal tail).
3. Separately: with an interactive instance running, run `uninstall.ps1`
   in a VM/scratch machine (admin, machine-wide!); record whether the
   interactive processes survive file deletion.

## Pass criteria (for the owning lane, suggested L6)

- FAIL today (predicted): decoy same-name process is killed (or: nothing
  verified); uninstall leaves interactive processes running.
- Fixed state: a user-facing stop stops ONLY the owned tree (graceful
  shutdown first, bounded wait, owned-tree verify, nonzero exit + loud
  message on survivors); uninstall refuses or stops interactive
  instances before deleting files. Both proven by a live run, not by
  script-text parsing.

## Handoff note (not my scope)

`CourierLauncher.cs` Ctrl+C path posts `/v1/shutdown` and returns
`handled=true`, but the 5s supervision loop restarts an exited
controller — so Ctrl+C likely never stops the launcher (window-close
still works via OS kill + Job Object). Read-only observation for the
L6/Grok owner of that file; not verified by execution.
