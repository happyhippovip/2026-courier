# Windows Packaging - Migration to V1 Worker Host
**Role:** L6 Windows Packaging / Native Acceptance Writer
**Scope:** lane/L6-windows-packaging

## 1. Goal
Complete the transition from the legacy `daemon.py` to the L3 `courier_worker` V1 runtime module, ensuring a zero-dependency clean Windows 11 packaging payload that uses the proper entry points.

## 2. Implementation
- **Courier Launcher:** Modified `CourierLauncher.cs` to invoke `python -m courier_worker.host` instead of executing a standalone `daemon.py`.
- **Packaging (`build_package.ps1`):** Updated the builder to package the entire `courier_worker` python module alongside the C# wrapper and embedded python, instead of copying `daemon.py`.
- **Cleanup:** Deleted the obsolete `daemon.py` from `scripts/windows_worker/`.

## 3. Verification
- Rebuilt `CourierWorker-v1.zip` via `build_package.ps1`.
- Compilation of the updated C# launcher succeeded.
- Verified that the ZIP contains the correct V1 `courier_worker` package module.

## 4. Evidence
- **Commit:** "L6: Target NEW V1 runtime (courier_worker) instead of legacy daemon.py"
- **Branch:** `lane/L6-windows-packaging`

Status: READY.
