# Windows Night Shift Handoff — 2026-09-24

This file preserves the current Windows-side operational context so agents do not need the full chat history.

## Git / ownership

- Local handoff branch: `ledger-reconciliation-final`
- Local handoff HEAD reported by Codex: `eba913b0cf909e550f7c8248b16ccc3ff23ba8fa`
- Local commit: `eba913b0 fix(windows): retain unresolved recovery markers`
- As of this handoff, that local SHA is not yet present on GitHub.
- GitHub `ledger-reconciliation-final` currently points to `adb9206adf9ab18568a3448049fc683185e6fc56`.
- Ledger remains read-only and owned by `Google-Antigravity`.
- `motor-eligibility-v1` remains read-only.
- Do not touch Mac files.
- Never overwrite foreign dirty files.
- No `git reset --hard`, `git clean -fd`, force push, or auto-merge to main.

## Phase order

P0 Bestand/Zuständigkeit
-> P1 Ledger/Wiederaufnahme
-> P2 Abschluss/Fortsetzungs-Semantik
-> P3 echter Betriebsnachweis
-> P4 small customer pilot
-> P5 product extensions
-> P6 economics

Do not skip P2/P3 gates.

## P2 — completed locally

Local commit `eba913b0` repaired Windows recovery semantics:

- unresolved effect markers survive failed result posting
- recovery is processed before new claims
- contradictory results remain durable and block further work
- no replay of confirmed external effect
- Windows torture and restart/resume tests were reported green

Previously reported tests:
- `tests/test_windows_runtime_torture.py`
- `tests/test_restart_resume_torture.py`

## P3 — currently blocked by foreign dirty server scope

Foreign-dirty files:
- `server/app.py`
- `server/run_waitress.py`
- `server/launch_server_hidden.vbs`

Rules while dirty:
- read-only only
- do not start a competing 8081 server
- do not blindly stop existing 8080 listeners
- do not duplicate the existing cutover monitor
- continue safe independent Windows work

Observed runtime:
- 127.0.0.1:8080 healthy
- 127.0.0.1:8081 unreachable
- two 8080 authorities were observed:
  - PID 19668: `python -m server.app`
  - PID 18532: Waitress wrapper

Known intended canonical 8081 path:
Hidden launcher -> `server/launch_server_hidden.vbs`
-> `server/run_waitress.py`
-> Waitress on 0.0.0.0:8081
-> verifier uses `COURIER_SERVER=http://127.0.0.1:8081`

A cutover monitor is already active. Do not race it.

## Verifier

- `CourierVerifier` scheduled task exists with Logon trigger.
- The running verifier was observed polling 8081 and receiving WinError 10061 while server remained on 8080.
- The detached verifier process automatic-recovery lifecycle is not yet proven.
- Original waitress wrapper used to couple verifier startup to server startup; foreign changes removed that coupling.

## Google / Antigravity recurring login popup

Confirmed symptom source:
- `agy.exe`
- console title: `Antigravity CLI (.gemini_alt Profile) - Google AI Pro Login`
- direct console parent was stopped previously by exact PID only
- no credential/profile files were deleted or changed

Important:
- recurring popup means a relaunch source exists
- do not repeatedly kill only `agy.exe`
- trace PID -> parent -> grandparent -> launcher/persistence source
- inspect exact persistence sources read-only before changing
- do not delete `.gemini` or `.gemini_alt`
- do not modify credentials
- no global cmd/python/chrome kills
- fixed means root cause proven + exact source changed + >=10 minute no-relaunch test + unrelated Courier/Muse activity still works

The Antigravity watcher may open Chrome on local port changes, but that is a separate browser-popup source and was not proven to be the Google-login source.

## Windows Muse Wall / supervisor

Legacy material exists outside the repo:
- `C:\Users\lol\TerminalWall\Terminal-Wall-Windows.ps1`
- `Muse Workspace.lnk` launches `Courier_Workspace.ps1`

Known legacy behavior:
- Terminal-Wall-Windows.ps1 defaults to 36 per side = 72
- Courier_Workspace.ps1 constructs 64 Windows Terminal panes immediately
- this is not an acceptable staged supervisor design

Required target:
- 64 logical READY slots
- `ACTIVE_PROVIDER_SLOTS=0` until account mapping is explicit
- staged levels: 1 -> 4 -> 8 -> 16 -> 32 -> 64
- per-slot state, lock, log, workdir, PID, process creation time
- exact-owned-process restart only
- duplicate prevention
- PID reuse protection
- stale lock reclaim
- corrupt state fails closed
- login recovery
- non-admin execution
- bounded logs
- no Google-login popup
- no server authority started from the wall

Slot names:
`MUSE-01` ... `MUSE-64`

Suggested state values:
READY / IDLE / WORKING / CHECKING / WAITING / BLOCKED / DONE / CRASHED

## Account mapping

Only local Gemini profile roots `.gemini` and `.gemini_alt` were observed. Six distinct identities must not be inferred.

Prepare placeholders only:
- ACCOUNT_A = P3/runtime
- ACCOUNT_B = Windows Muse wall
- ACCOUNT_C = recovery/regression
- ACCOUNT_D = independent Courier queue
- ACCOUNT_E = QA/review
- ACCOUNT_F = release/ledger read-only

Keep all UNBOUND until Dennis explicitly maps/approves identities.

## Dirty-tree rule

A dirty main worktree is a scope constraint, not a global blocker.

If main worktree is dirty:
1. classify dirty files and ownership
2. find clean/unowned scope
3. use read-only analysis where writing is unsafe
4. use an isolated worktree/branch for independent code fixes when safe
5. never overwrite foreign dirty state

Old CHECK_T1..CHECK_T7 assignment slots are not a global capacity limit. For local planning, agents may use `WIN_NIGHT_###` IDs without writing them to the ledger.

## Safe Windows backlog while P3 is blocked

- Muse supervisor tests
- 64-slot simulation without provider calls
- duplicate PID/lock regression
- PID + process creation-time ownership
- crash/restart recovery
- corrupt-state fail-closed
- graceful shutdown
- process-tree cleanup
- temp-dir isolation
- Windows path/encoding/subprocess quoting
- PowerShell quoting
- long-path behavior
- log rotation and bounded logs
- CPU spin/restart-loop protection
- orphan child cleanup
- slot state persistence
- capacity governor tests
- 1/4/8/16/32/64 synthetic canary
- Windows Terminal layout validation
- Wall duplicate-start prevention
- Scheduled Task configuration validation
- non-admin startup
- login-resume simulation
- supervisor doctor/status/dry-run/repair commands
- startup diagnostics
- exact-PID termination tests
- unrelated-process survival tests
- Windows runtime documentation/runbook
- skipped/flaky Windows-test audit
- coverage gaps

## Operating loop

CHECK
-> OWNERSHIP
-> ONE MISSION
-> REPRODUCE
-> ROOT CAUSE
-> RED
-> MINIMAL FIX
-> GREEN
-> REGRESSION
-> `git diff --check`
-> scoped commit
-> proof
-> next mission

If blocked in one scope, move to the next independent safe mission.

Do not report `SAFE_WORK_REMAINING=NONE` merely because:
- the main worktree is dirty
- old task slots are occupied
- one writer scope is blocked
- P3 is blocked

## Morning target

Preferred morning report:

```text
HEAD=
COMMITS=
WINDOWS_MUSE_SUPERVISOR=
WINDOWS_MUSE_WALL=
SLOTS_READY=
ACTIVE_PROVIDER_SLOTS=
64_READY=
MAX_SIMULATED_SLOTS=
AUTOSTART=
LOGIN_RECOVERY=
DUPLICATE_PROTECTION=
PID_CREATION_TIME_PROTECTION=
PROCESS_ISOLATION=
SOAK_TEST=
P3_STATUS=
8080_STATUS=
8081_STATUS=
VERIFIER_STATUS=
GOOGLE_LOGIN_POPUPS=
FILES_CREATED=
FILES_CHANGED=
TESTS=
OPEN_BLOCKERS=
NEXT_SAFE_ACTION=
DENNIS_ACTION_REQUIRED=
```

The objective is that Windows login eventually yields a ready Courier/Muse work surface without manual terminal startup, while server authority, recovery, ownership, and provider account boundaries remain safe.
