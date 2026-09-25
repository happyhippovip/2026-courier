# Windows Antigravity startup/recovery authority

One canonical way to keep **exactly one** Google Antigravity instance (on the
existing signed-in Google profile) running on the Windows PC.

## Activate (once)

Double-click `install.cmd`. No admin rights are needed, and running it again is safe.

That registers one Scheduled Task, `\CourierAntigravitySupervisor`:

- It runs at logon and every 15 minutes, hidden, under the current user.
- It uses `pythonw`, so no console window opens.
- `MultipleInstancesPolicy=IgnoreNew` plus the supervisor's file lock mean a
  second copy can never run.

## What the supervisor does (every 30 s)

| Observed | Action |
|---|---|
| Healthy (main process + language server + reachable local listener) | nothing |
| Started less than `startup_grace_seconds` ago | wait, never spawn a second copy |
| Antigravity not running (crash, midnight kill, stale PID) | start one, minimized, without taking focus |
| Running but language server / UI missing for 4 checks | stop only that tree, start one |
| Starts keep failing | exponential backoff (15 s → 600 s), at most 5 starts per hour, then `GAVE_UP` until the window refills |

The UI port is discovered live from the Antigravity process tree on every
check. If the port changes, the supervisor follows it instead of restarting.
It never opens a browser, never creates or deletes a profile, and never
logs credentials: all log output is redacted.

## Files

- `supervisor.py`: supervisor + `status` / `e2e` / `install` / `uninstall` CLI
- `installer.py`: Scheduled Task XML, venv (psutil), reversible disabling of
  duplicate launchers. Launchers that also start Muse are only reported,
  never touched.
- `config.example.json`: seeded into `%LOCALAPPDATA%\CourierAntigravity\config.json`
  on first install from the running Antigravity (its exe and `--user-data-dir`).
  An existing config is never overwritten.
- `status.cmd`: read-only status. `status.cmd --e2e` also sends one harmless
  agent request (`agy -p "Reply with exactly: AGENT_OK"`).
- `uninstall.cmd`: removes the task. `--restore` re-enables the launchers
  that install disabled.

Runtime state lives in `%LOCALAPPDATA%\CourierAntigravity\`: `state.json`,
`supervisor.log`, `disabled_authorities.json`.

Does not touch P3 (`server/app.py`, `server/run_waitress.py`,
`server/launch_server_hidden.vbs`) or the separate `CourierWindowsWorker` task.

Tests: `python -m unittest tests.test_windows_antigravity_supervisor`
