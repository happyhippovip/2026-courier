# Windows Productization Report

## 1. Windows Host Truth
* **Runtime:** Python 3.14.7 is available via `uv`.
* **Repo Path:** `c:\Users\lol\2026-workspace\2026-courier`
* **Worker Starts:** Yes, via `bootstrap.ps1` -> `daemon.py`.
* **Worker Registration & Heartbeat:** Functional, provided the backend is reachable (fails closed if `COURIER_SERVER` is offline).
* **Queue/Status:** `status.bat` is brittle. It currently searches for `python.exe` universally without distinguishing the daemon, leading to false positives.
* **Service/Scheduled Task:** The scheduled task (`CourierWindowsWorker`) requires UAC to install. If UAC is missing, it falls back to a background hidden process.
* **Backend Reachable:** No, currently offline on this host. Default points to `http://192.168.178.162:8080`.
* **Shutdown:** `stop.bat` attempts to kill via `WINDOWTITLE eq CourierWindowsWorker*`. This fails to kill the UAC-fallback hidden process, causing zombie workers.
* **Restart:** Handled by scheduled task on boot (if UAC succeeded) or not at all (if fallback was used).

## 2. Terminal Steps Still Required
A user currently must manually:
1. Install `uv` and ensure it's in PATH.
2. Open PowerShell.
3. `cd` into the correct repository path (`scripts/windows_worker/`).
4. Execute `.\bootstrap.ps1`.
5. Provide the Server URL and API Key via prompt if not in args.
6. Manually hunt down zombie `python.exe` processes because `stop.bat` fails on the fallback path.

## 3. Missing for Courier.exe
* **Auto-Elevation:** A mechanism to automatically request UAC to install the scheduled task rather than silently falling back to an unmanageable hidden process.
* **Process Tracking:** A reliable PID file or Mutex tracking so `status` and `stop` work definitively, regardless of how the daemon was started.
* **GUI / System Tray:** A visual indicator (system tray) to prompt for the Server IP and API Key if they are missing, rather than a hidden console prompt.
* **Stdout/Log redirection:** The hidden fallback process swallows stdout. We need proper logging to `worker.log` for debugging and bootstrap wait-loops.

## 4. MAC Interference
**NONE.** All tests and analyses were strictly bounded to Windows-local scripts and states.

## 5. Readiness
**PARTIAL.** The python logic (`daemon.py`) is highly robust, but the lifecycle wrappers (`bootstrap.ps1`, `stop.bat`, `status.bat`) are fragile and leak zombie processes.
