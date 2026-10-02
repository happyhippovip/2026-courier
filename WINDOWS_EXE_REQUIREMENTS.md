# Windows Courier.exe Requirements

## 1. Core Executable Requirements
* **Language/Architecture:** Recommend Go or Rust for a standalone executable to avoid requiring the user to install Python/uv, or PyInstaller if Python is strictly required. A single statically linked binary is ideal.
* **Privilege Elevation:** Must contain an Application Manifest specifying `requireAdministrator` to ensure the Scheduled Task can be created reliably, avoiding the broken hidden-process fallback.
* **Idempotent Installation:** Launching the EXE should automatically detect if `CourierWindowsWorker` scheduled task is missing or outdated and register it.

## 2. Configuration & Discovery
* **GUI Prompt:** If `config.json` lacks `COURIER_SERVER` or `COURIER_API_KEY`, the EXE must spawn a native Windows dialog prompting for these values before proceeding. It cannot rely on console `Read-Host`.
* **System Tray Indicator:** The worker should run a lightweight system tray icon that indicates:
  - Worker ID
  - Current Status (Online/Offline/Busy)
  - Options: "Stop Worker", "Change Server/Key", "Exit"

## 3. Process Management & Tracking
* **PID File:** The worker must write its PID to a known location (e.g., `%APPDATA%\Courier\worker.pid`).
* **Clean Shutdown:** The "Stop Worker" action must read the PID file and terminate exactly that process tree, rather than using a wildcard `taskkill /IM python.exe`.
* **Zombie Prevention:** During startup, if a PID file exists, the EXE must verify if that PID is actually Courier. If it is, avoid starting a duplicate. If it's a dead/unrelated process, overwrite the PID file and start.

## 4. Logging & Diagnostics
* **Proper Redirection:** Instead of swallowing stdout in a hidden process, the EXE must route all logs to `%APPDATA%\Courier\logs\worker.log`.
* **Health Check API:** The EXE should perform an HTTP GET to the backend to verify reachability before committing to the background daemon loop, providing immediate visual feedback to the user if the server is unreachable.
