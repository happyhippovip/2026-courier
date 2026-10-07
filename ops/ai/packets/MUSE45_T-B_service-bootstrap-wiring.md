# MUSE-45 T-B — Service/bootstrap wiring map (static, read-only)

MISSION=COURIER_LIVE_SHOW_CONTINUE, slot MUSE-45, date 2026-09-26.
Method: static reads only (shell DOWN). Every edge installer -> launcher ->
interpreter -> module verified by reading both ends. No file modified.

## Wiring map (OBSERVED)

| Installer | Launcher | Interpreter / venv | Module | Module exists |
|---|---|---|---|---|
| scripts/install_motor_service.ps1 (SchedTask CourierMotor, AtLogon) | scripts/start_motor.bat | .venv_service python | server.app + scripts.courier_github_dispatcher + scripts.courier_watchdog | YES x3 |
| scripts/install_verifier_service.ps1 (SchedTask CourierVerifier, AtLogon) | scripts/start_verifier.bat | .venv_service python | scripts.courier_verifier | YES |
| server/install_server_service.ps1 (HKCU Run CourierServer + immediate WMI start) | GENERATES server/run_waitress.py + server/launch_server_hidden.vbs, runs via pythonw | .venv_service pythonw (uv venv created by installer) | waitress serve(server.app, 0.0.0.0:8080) | YES (generated at install) |
| scripts/windows_worker/install_service.ps1 (SchedTask CourierWindowsWorker, AtLogon) | scripts/windows_worker/start.bat -> run_loop.bat (5s respawn loop) | bare `uv run` | scripts/windows_worker/daemon.py | YES |
| scripts/windows_muse_wall/install_desktop_shortcuts.ps1 | launch_32_auto.ps1 -Target N [-Yolo] | system powershell | probe + supervisor + wt wall | YES (mapped earlier) |

Operational worker stop/status: status.bat (CIM query for daemon.py cmdline),
stop.bat (CIM terminate on cmdline match `daemon.py|run_loop.bat`).

## Findings (for owner; NOT fixed here)

- F1 MEDIUM: `server/install_server_service.ps1` rewrites `server/run_waitress.py`
  and `server/launch_server_hidden.vbs` via Set-Content on EVERY run. These two
  files are P3 read-only owned. Installer-owned generation vs P3 read-only is an
  unresolved ownership collision. Scope: P3/Google.
- F2 MEDIUM: two server launch paths both bind port 8080: motor path
  (`python -m server.app`, Flask dev on 127.0.0.1 per daemon log) vs server-service
  path (waitress on 0.0.0.0). If both installed, second binder fails. Observed
  live server was the Flask-dev one; which path SHOULD own 8080 is undecided.
  Needs machine check by owner.
- F3 MEDIUM: `scripts/windows_worker/stop.bat` kills by command-line substring
  match (`daemon.py|run_loop.bat`). This can terminate non-owned processes (e.g. an
  editor with daemon.py in its command line, or a mac_worker daemon). Exact-identity
  stop (`stop_safe.py`, PID+create_time) exists and is tested
  (tests/test_windows_daemon_completeness.py) but the operational stop path bypasses
  it. Recommend owner routes stop through stop_safe.py. No fix by me (Google scope,
  needs shell to test).
  UPDATE (T-G cross-check): F3 is already test-pinned as KNOWN legacy debt:
  tests/test_windows_daemon_completeness.py:209 test_stop_bat_has_broad_kill_warning
  documents stop.bat as "the legacy approach" and asserts the broad match is still
  there; :199-207 pin stop_safe.py to lock-file identity. So: acknowledged, not news.
- F4 LOW: orphaned launchers, zero references in scripts/server/ops/docs:
  `server/start_server.bat` (third server-launch variant, `uv run -m server.app`)
  and `scripts/windows_worker/start.py` (detached daemon launcher appending to the
  SAME logs/worker.log as run_loop.bat -> dual-launch would interleave). Owner
  call: keep-document or delete.
- F5 LOW: three venv resolution strategies in one repo: motor/verifier pin
  `.venv_service`; worker run_loop uses bare `uv run`; start_server.bat uses
  `uv run --with flask --with keyring`. Same-machine drift risk. Owner call.

## Verdict

All installer->entry edges resolve to real files; no dangling launcher. Findings
F1-F5 are ownership/consistency risks for Google/P3, recorded here only.
