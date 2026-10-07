# Windows Packaging - Configuration Linking for V1 Worker Host
**Role:** L6 Windows Packaging / Native Acceptance Writer
**Scope:** lane/L6-windows-packaging

## 1. Goal
Connect the parameters installed by `install.ps1` to the newly migrated V1 runtime (`courier_worker.host`), which now expects CLI flags and a specific token file instead of the legacy `config.json` approach.

## 2. Implementation
- **Configuration (Installer):** Modified `install.ps1` to write the `COURIER_API_KEY` directly to `C:\ProgramData\CourierWorker\run\controller.token`, the exact path expected by the V1 worker host `_default_client`.
- **Launcher CLI Arguments:** Modified `CourierLauncher.cs` to read `C:\ProgramData\CourierWorker\config.json`, extract `COURIER_SERVER` and `COURIER_WORKER_ID` via simple string parsing, and pass them as `--home`, `--controller`, and `--worker-id` arguments when invoking `python -m courier_worker.host`.

## 3. Verification
- Mocked an installed environment with `config.json` and `controller.token`.
- Recompiled `Courier.exe` and tested invocation. 
- Logged verification shows that `uv run python -m courier_worker.host` accurately picks up the arguments, successfully invokes the V1 service loop, and correctly fails over connection timeouts on `http://localhost:8080`, confirming arguments are fully wired.

## 4. Evidence
- **Commit:** "L6: Pass correct configuration arguments to V1 worker host from CourierLauncher"
- **Branch:** `lane/L6-windows-packaging`

Status: READY.
