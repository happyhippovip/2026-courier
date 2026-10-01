# W09 STATIC PREP PACKET — exact-SHA runtime proof (commands + evidence checklist)

Status: PREP ONLY. No proof claimed (shell down; no live process access).
Owner of W09 execution: Antigravity/Google. This file lives in MUSE-45's slot
dir so it cannot collide; move to ops/ai/packets/ only on owner request.

## 0. Objective (from WINDOWS_CONTINUOUS_WORK.yaml W09 + RC checkpoint)
Establish process -> executable -> worktree -> exact SHA for the canonical
Windows runtime; compare serving SHA vs tested SHA vs acceptance-bound SHA;
mark old physical evidence STALE if runtime-affecting code changed. Separately
resolve RC Motor question A (Motor embedded in OS-owned server) vs B (separate
persistent owner missing) by OBSERVED process/thread ownership.

## 1. Process identity capture (per runtime: server, verifier, motor, worker)
PowerShell (admin not required for own-user processes):
  Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|pythonw' } |
    Select-Object ProcessId, ParentProcessId, ExecutablePath, CommandLine,
      CreationDate | Format-List
Evidence: full CommandLine (must show script path + worktree), PID, PPID,
CreationDate. Repeat for wscript.exe (server VBS path) and cmd.exe ancestors.
Scheduled-task provenance:
  Get-ScheduledTask CourierMotor, CourierVerifier, CourierWindowsWorker |
    Get-ScheduledTaskInfo | Select-Object TaskName, LastRunTime, LastTaskResult
  schtasks /query /tn CourierMotor /v /fo LIST   # shows executable + user
Server-service provenance:
  Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
  # expect: CourierServer -> wscript.exe "<worktree>\server\launch_server_hidden.vbs"

## 2. Executable -> worktree binding
- From CommandLine: script path must resolve inside ONE worktree; record
  resolved absolute worktree path (Resolve-Path).
- From VBS: read server\launch_server_hidden.vbs CurrentDirectory line.
- From .bat chain: start_motor.bat does cd /d "%~dp0\.." — record %~dp0.
- CWD check per PID: (Get-Process -Id $pid).StartInfo.WorkingDirectory is NOT
  reliable post-hoc; prefer CommandLine + handle.exe only if already installed
  (do NOT install new tools silently — human gate for new binaries).

## 3. Worktree -> exact SHA
In the OBSERVED worktree (not assumed repo path):
  git rev-parse HEAD                    # SERVING_SHA
  git status --porcelain                # must be empty for a bound run
  git diff HEAD --stat                  # any output => unbound worktree
  git log -1 --format='%H %ci %s'
Record separately: SERVING_SHA, TESTED_SHA (SHA the T-evidence ran against),
ACCEPTANCE_BOUND_SHA (frozen at proof start). Rule: all three equal AND status
clean, else the run is UNBOUND (may still run, but cannot be cited as proof).

## 4. Stale-proof decision rule
- List runtime-affecting paths: server/app.py, server/run_waitress.py,
  scripts/courier_continue.py, scripts/agent_handoff_ledger.py,
  scripts/courier_verifier.py, scripts/courier_github_dispatcher.py,
  scripts/courier_watchdog.py, scripts/*/daemon.py, installers + .bat chain.
- git diff TESTED_SHA..SERVING_SHA -- <those paths> : any output =>
  prior physical evidence STALE, new run required. Doc/test-only diff =>
  evidence stands, note the delta.

## 5. OS-ownership + A/B protocol (RC steps 1-3)
- PPID chain: runtime PIDs must parent to services.exe/svchost/taskengw
  (task) or wscript detached (server), NOT to a conhost/terminal owned by
  the interactive agent.
- Terminal-exit test: start runtime via its registered mechanism ONLY
  (scheduled task / HKCU Run, never a foreground shell), close ALL
  interactive terminals, re-capture section 1 from a FRESH logon shell:
  same PIDs + same CreationDate = survives terminal exit.
- A/B: if Motor transitions (dispatch/reconcile/READY) occur while ONLY
  server.app + verifier processes exist (no separate motor PID) => A
  (embedded). If a distinct persistent motor-owned process performs them
  => A-variant with named owner. If transitions need a manually started
  courier_continue process => B (separate owner missing) and that IS the
  first causal blocker. Observe, do not assume.
- Logoff boundary (known from T8/F-T8-2): AtLogon+Interactive tasks and
  HKCU Run do NOT survive logoff. The proof run MUST keep the Windows
  session logged on; record logon session id (query session) in evidence.

## 6. Pass/fail + evidence package
PASS requires: single worktree, SERVING==TESTED==BOUND, status clean,
PPID chain OS-owned, terminal-exit survival demonstrated, A/B resolved by
observation, >=10 tasks >=2 workers USER_CONTINUE=0 per RC (separate run).
Evidence files: process capture (txt), task query (txt), git rev-parse/
status/diff (txt), decision table (md). No screenshots as primary evidence.

## 7. Known blockers for THIS session (why prep-only)
Shell runner down (sandbox setup fails pre-execution); escalated shell
denied. No git, no Get-Process, no task queries executable from here.
Hand to a shell-capable Windows session.
