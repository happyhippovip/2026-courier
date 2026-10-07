# Windows Packaging - Iteration 91
**Role:** L6 Windows Packaging / Native Acceptance Writer
**Scope:** lane/L6-windows-packaging

## 1. Goal
Implement Priority 1, 4, 5, 6 from the L6 Windows Packaging scope:
1. Windows launcher
4. Windows Job Object containment where appropriate
5. clean shutdown
6. zero orphan Courier processes

## 2. Implementation
Created `scripts/windows_worker/launcher/CourierLauncher.cs`, a native C# 5.0 application that:
- Acts as a native `Courier.exe` Windows executable (`/target:winexe`).
- Creates a Windows Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) to ensure all subprocesses (including the Python runtime and daemon child processes) are strictly bound to the launcher's lifecycle.
- Checks for an embedded python distribution (future priority) and falls back to `uv run python` if not found.
- Updated `start.bat` and `stop.bat` to simply use `Courier.exe`.
- Updated `install_service.ps1` to register the native `.exe` instead of the batch file.

## 3. Verification
- Compiled successfully with native `csc.exe`.
- `Courier.exe` successfully launched the Python `daemon.py`.
- Exiting/killing `Courier.exe` gracefully tears down all child processes (no orphans left).
- Running `pytest -q tests/test_windows_worker_contract.py tests/test_windows_worker_binding.py` confirmed 100% pass rate. Existing worker contracts remain fulfilled without breakage.

## 4. Evidence
- **Commit:** `6a917b07` "Implement native Windows C# Launcher with Job Object containment"
- **Branch:** `lane/L6-windows-packaging`

Status: READY. Moving to the next item (e.g. installer/packaging).
