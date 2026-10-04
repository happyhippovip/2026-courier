# Windows Packaging - Iteration 92
**Role:** L6 Windows Packaging / Native Acceptance Writer
**Scope:** lane/L6-windows-packaging

## 1. Goal
Implement Priority 2, 7, 9, 10, 11, and 12 from the L6 Windows Packaging scope:
2. correct install/runtime paths
7. local logs
9. packaging / EXE
10. installer
11. uninstall preserving user data by default
12. no Python required on clean target

## 2. Implementation
- **Paths & Logging (`daemon.py`):** Updated to use `%PROGRAMDATA%\CourierWorker` for production storage of `state`, `logs`, and `config.json` while maintaining developer fallback to `__file__.parent`. Setup native Python logging hooked to stdout/stderr.
- **Packaging (`build_package.ps1`):** Wrote a comprehensive packager that compiles `Courier.exe`, downloads the official Python 3.11 embeddable distribution, bundles `daemon.py` alongside the install scripts, and zips it all into `CourierWorker-v1.zip`.
- **Installer (`install.ps1`):** Created a zero-dependency PowerShell installer that runs elevated, registers the Service Account Scheduled Task, copies binaries to `C:\Program Files\CourierWorker`, and prompts the user for setup credentials saving them cleanly to `%PROGRAMDATA%\CourierWorker\config.json`.
- **Uninstaller (`uninstall.ps1`):** Updated the uninstaller to stop/unregister the Scheduled Task and delete the Program Files installation directory while explicitly preserving user data in `%PROGRAMDATA%`.

## 3. Verification
- Compiled and built `CourierWorker-v1.zip` via `build_package.ps1`.
- Tests pass locally. All windows worker tests run cleanly. No regressions in existing Windows adapter contracts (`test_windows_worker_contract.py`, `test_windows_worker_binding.py`, `test_windows_worker_daemon_uncovered.py`).

## 4. Evidence
- **Commit:** "Implement zero-dependency Windows package, installer, and proper paths"
- **Branch:** `lane/L6-windows-packaging`

Status: READY. Moving to the next item in the acceptance priority.
