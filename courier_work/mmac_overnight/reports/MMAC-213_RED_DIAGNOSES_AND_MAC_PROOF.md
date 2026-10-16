# MMAC-213 — #253/#254 red-CI root causes + #256 local mac proof (read-only + isolated run)

Base `origin/integration/v1` = `f425d328`. Zero branch mutations (one isolated /tmp worktree, removed after).

## FINDING-253-WIN-COPY (owner: Cursor L6, live — no patch)
Windows CI red while ubuntu green (run 37723730386). File-blocking the destination (regular file at the `ProgramFiles` path) fails the copy on POSIX but not on Windows (`assert 0 != 0`); and the positive test's staged marker is absent after a "successful" copy (FileNotFoundError). Same systemic note as #251: docstring claims "not a Windows machine" while the windows matrix runs the file.

## FINDING-254-WIN-RM (owner: Cursor L6, live — no patch)
Two failures (run 37723811567): (1) definitive test bug — `os.geteuid()` does not exist on Windows (fix: getattr guard); (2) exit 0 + "Uninstall complete." printed while the install directory remains — the Test-Path re-check is blind to something on Windows (path-normalization mismatch between removal and re-check views is the prime suspect; exact mechanism needs a Windows shell).
Owner fix options filed in the JSON record.

## Local proof: #256 mac status 8/8 green on Intel Mac
`tests/test_mac_worker_verified_status.py` executed in an isolated worktree of `bf4412126`: all four launchctl states, JSON CLI, no-grep enforcement, and fail-closed install — 8 passed in 3.34s on real macOS hardware. Worktree removed; live lane untouched.
