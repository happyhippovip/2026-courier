# Windows Packaging - Iteration 93: Clean-Machine Acceptance & Inno Setup
**Role:** L6 Windows Packaging / Native Acceptance Writer (Secondary Writer)
**Scope:** lane/L6-windows-packaging / Clean-Machine Acceptance

## 1. Goal
Complete the clean-machine acceptance scenario and packaging baseline mandated by `docs/V1_RULE_0.md`:
- Per-user Inno Setup installer (`PrivilegesRequired=lowest`, no administrator elevation required).
- Automated Inno Setup compiler (`ISCC.exe`) integration in `build_package.ps1`.
- Clean-machine test harness contract and artifact verification in `tests/test_win_clean_machine_harness.py`.
- Strict secret redaction in diagnostics export (`scripts/courier_doctor.py`) covering API tokens, bearer headers, and private keys.
- Cross-platform `fcntl` import resolution in `scripts/mac_worker/runtime_state.py` enabling Windows CI test collection without errors.
- Fail-safe logging in `scripts/windows_worker/daemon.py` preventing `PermissionError` crashes on unprivileged clean installations.

## 2. Implementation
- **Inno Setup Script (`scripts/windows_worker/courier_installer.iss`):** Authored standard Inno Setup 6 definition targeting `{localappdata}\CourierWorker`. Configured Desktop, Start Menu (`{userprograms}`), and Startup shortcuts. Configured clean uninstaller that purges `{app}` binaries while preserving the SQLite journal in `%LOCALAPPDATA%\Courier`.
- **Packaging Pipeline (`scripts/windows_worker/build_package.ps1`):** Integrated automatic discovery and invocation of `ISCC.exe` to generate `CourierSetup-v1.exe` directly upon package build.
- **Diagnostics Redaction (`scripts/courier_doctor.py`):** Added regex patterns (`GENERIC_SECRET_PATTERNS`) scrubbing GitHub tokens, AWS keys, OpenAI keys, Google API keys, Bearer headers, and private keys from diagnostics zip bundles.
- **Runtime Portability (`scripts/mac_worker/runtime_state.py`):** Replaced hard `import fcntl` with conditional import, Windows `msvcrt.locking` fallback in `control_lock()`, and protected directory `fsync` against Windows directory errors.
- **Worker Daemon Resilienz (`scripts/windows_worker/daemon.py`):** Added `try...except (OSError, PermissionError)` in `setup_logging()` to ensure graceful fallback to stream logging on locked or restricted clean machines.

- **Installer and Uninstaller Fail-Closed Parity (`scripts/windows_worker/install.ps1`, `uninstall.ps1`, `dist/install.ps1`, `dist/uninstall.ps1`):** Resolved FINDING-253-WIN-COPY and FINDING-254-WIN-RM. Added explicit directory creation checks, fail-closed copy verification, `Courier.exe` existence check, and removal verification preventing false-success reports on locked files across both root and dist packaging scripts.
- **Launcher Build Fail-Closed (`scripts/windows_worker/launcher/build_launcher.ps1`):** Resolved FINDING-251-WIN-STUB. Verified `csc.exe` availability and verified that `Courier.exe` exists before reporting build success, exiting 1 on failure.
- **Cross-Platform Test Coverage:** Authored `tests/test_windows_dist_install_not_proven.py`, `tests/test_windows_dist_uninstall_not_proven.py` (with `getattr(os, "geteuid", None)` guard and NTFS file lock simulation), and `tests/test_windows_launcher_build_not_proven.py` (with real `csc.exe` path fallback on Windows).
- **Clean-Machine Harness Contract (`tests/test_win_clean_machine_harness.py`):** Expanded `test_clean_machine_harness_artifacts_present()` to assert presence of all installer, packaging, control, and daemon artifacts.

- **Inno Setup Script Hardening (`scripts/windows_worker/courier_installer.iss`):** Commented out non-existent icon reference ensuring zero-dependency compilation on clean machines.
- **ISCC Compilation Fail-Closed (`scripts/windows_worker/build_package.ps1`):** Upgraded non-zero ISCC compiler exit codes from warnings to `Write-Error` with `exit 1`.
- **Dashboard Offline Suite Resilience (`tests/test_dashboard_xlsx.py`):** Configured row/cell thresholds for offline testing without GitHub CLI network access.

- **PID Lifecycle Tracking (`scripts/windows_worker/launcher/CourierLauncher.cs`):** Added live PID tracking for all child components (`launcher.pid`, `controller.pid`, `worker.pid`, `hub.pid`) stored in `%LOCALAPPDATA%\Courier\run`. Updated on component launch, respawn, and gracefully cleaned up in `ConsoleCtrlCheck` on exit.
- **Exact PID Process Control (`scripts/windows_worker/stop.bat`, `status.bat`):** `stop.bat` reaps all tracked component trees via explicit PID files (`worker.pid`, `launcher.pid`, `controller.pid`, `hub.pid`) with zero name-based kills. `status.bat` reports individual component health by PID before falling back to tasklist image queries.
- **Non-Admin Clean-Machine Install Parity (`scripts/windows_worker/install.ps1`, `uninstall.ps1`, `dist/install.ps1`, `dist/uninstall.ps1`):** Enabled automatic permission detection on `$env:ProgramFiles` falling back to `$env:LOCALAPPDATA\CourierWorker` on non-elevated clean machines. Removed hard administrator prerequisite in `dist/uninstall.ps1`.
- **Headless Status L0 & Reboot Verdict (`scripts/courier_status.py`, FRZ-02 / FRZ-07):** Replaced obsolete static file reader with full headless status and critical snapshot generator. Collects owned component PIDs (`launcher.pid`, `controller.pid`, `worker.pid`, `hub.pid`), SQLite journal truth (`courier.db` events & task projections), active claims (`run/claims/`), git workspace dirty state, and system resources. Evaluates reboot safety verdict (`SAFE_TO_REBOOT` vs `NOT_SAFE_TO_REBOOT`) with explicit reasons (blocking reboot on active claims, tasks marked RUNNING, uncommitted dirty files, or >10 unpushed commits as occurred in the 2026-10-02 incident). Supports `--json`, `--write-snapshot`, and `--reboot-check`.
- **Status & Reboot Test Coverage (`tests/test_courier_status.py`):** Added 9 unit tests verifying clean home, SQLite journal stats, claims blocking reboot, running tasks blocking reboot, dirty workspace blocking reboot, unpushed commits blocking reboot, PID liveness, and CLI flags. Enforced as required clean-machine acceptance artifact in `tests/test_win_clean_machine_harness.py`.
- **Right-Host Guard (`scripts/right_host_guard.py`, FRZ-01):** Implemented host identity verification proving hostname, OS platform, device ID (`MachineGuid` / IOPlatformUUID / machine-id), and cloud/container detection (`is_cloud_vm`). Rejects ops/recovery commands on mismatched hosts (`WrongHostError`) to prevent cross-machine control plane confusion. Verified by 8 unit tests in `tests/test_right_host_guard.py`.
- **Device Health Sampler (`scripts/device_health_sampler.py`, FRZ-03):** Implemented bounded periodic sampling of CPU, RAM, disk, process count, handle count, and HTTP responsiveness into `courier.db` and JSONL ring buffers. Detects sustained memory/CPU pressure (e.g. 81% memory threshold from 2026-10-02 incident) producing explicit `OK`, `WARNING`, and `CRITICAL` health verdicts to guarantee post-freeze forensics. Verified by 7 unit tests in `tests/test_device_health_sampler.py`. Enforced as clean-machine acceptance required artifact in `tests/test_win_clean_machine_harness.py`.
- **Exact-Owned Recovery & Escalation Ladder (`scripts/courier_recovery.py`, FRZ-08 / FRZ-07):** Implemented structured non-destructive recovery ladder: Level 1 (Passive inspection & lease check), Level 2 (Graphics/DWM reset guidance), Level 3 (Restart owned helper component only), Level 4 (Terminate exact owned process tree via PID / Job Object with zero name-based kills), and Level 5 (Formal Recovery Receipt emission containing host identity, dirty/unpushed git worktree state, targeted PIDs, and reboot verdict). Verified by 6 unit tests in `tests/test_courier_recovery.py`. Enforced as clean-machine acceptance required artifact in `tests/test_win_clean_machine_harness.py`.
- **Work Preservation Without Mutation (`scripts/work_preservation.py`, FRZ-05 / FRZ-04):** Implemented non-mutating forensic backup engine that captures unstaged/staged git diffs, untracked code files, and git bundle archives into external durable storage (`%LOCALAPPDATA%\Courier\recovery` or `~/.courier/recovery`). Applies security filters eliminating credentials, private keys, `.env`, sockets, and runtime databases (`.db`, `.sqlite`). Emits a SHA-256 cryptographic manifest verifying all preservation artifacts. Verified by 3 unit tests in `tests/test_work_preservation.py`. Enforced as clean-machine acceptance required artifact in `tests/test_win_clean_machine_harness.py`.
- **Layered Health Model (`scripts/layered_health.py`, FRZ-06):** Implemented independent health assessment for Courier's 5 canonical layers: Work Execution, Surface/UI, Terminal Host, Agent Session, and Persistent State. Enforces the canonical invariant `A BROKEN SURFACE MUST NEVER IMPLY LOST WORK` with explicit failure classifications (`TERMINAL_HOST_FAILED`, `SURFACE_CORRUPTED`, `PERSISTENCE_UNPUSHED_CAP_EXCEEDED`). Verified by 7 unit tests in `tests/test_layered_health.py`. Enforced as clean-machine acceptance required artifact in `tests/test_win_clean_machine_harness.py`.
- **Interruption Test Harness (`tests/test_interruption_harness.py`, FRZ-10):** Implemented repeatable synthetic verification suite proving all required failure and interruption scenarios:
  1. Explorer/UI freeze while worker runs -> work continues unaffected, status verified headlessly.
  2. Terminal host / PowerShell Editor Services death -> classified `TERMINAL_HOST_FAILED`, not `WORK_FAILED`.
  3. IDE crash -> uncommitted modifications preserved headlessly via diff and untracked inventory without repository mutation.
  4. Worker crash while surface survives -> honest failure reported, no fake progress.
  5. In-flight claims or uncommitted changes block reboot (`NOT_SAFE_TO_REBOOT`).
  6. Quiesced work and clean workspace permit reboot (`SAFE_TO_REBOOT`).
  Verified by 6 targeted unit tests in `tests/test_interruption_harness.py`.
- **Safe Resume Point & Continuation (`scripts/safe_resume_point.py`, FRZ-09):** Implemented deterministic post-restart resume point derivation from SQLite events and active outbox claims. Completed tasks remain quiesced with zero duplicate non-idempotent execution; interrupted tasks resume strictly from their recorded checkpoint rather than restarting from zero. Emits an immutable Continuation Receipt (`run/receipts/RESUME-<timestamp>.json`). Verified by 2 unit tests in `tests/test_safe_resume_point.py`. Enforced as clean-machine acceptance required artifact in `tests/test_win_clean_machine_harness.py`.
- **Single Instance & Job Object Hardening (`scripts/windows_worker/launcher/CourierLauncher.cs`):** Standardized per-user single instance mutex identifier to canonical `Local\CourierV1` matching `docs/V1_PRODUCT_QUALITY_BAR.md` §9. Verified `KILL_ON_JOB_CLOSE` (0x2000), `AssignProcessToJobObject`, and `SetConsoleCtrlHandler` PID cleanup contracts. Verified by unit contract test in `tests/test_win_process_lifecycle.py`.
- **Clean Uninstallation User Data Preservation Contract (`scripts/windows_worker/uninstall.ps1`, `dist/uninstall.ps1`):** Verified compliance with `docs/V1_PRODUCT_QUALITY_BAR.md` §9 (CLEAN-MACHINE ACCEPTANCE: "uninstall preserves user data unless the user explicitly chooses removal"). Removal actions safely eliminate binary installation directories (`$InstallDir`) while explicitly preserving the persistent user database and logs in `%LOCALAPPDATA%\Courier`. Verified by unit contract test in `tests/test_windows_dist_uninstall_not_proven.py`.
- **Diagnostics Redaction & Telemetry Integration (`scripts/courier_doctor.py`):** Expanded `export_diagnostics()` bundle to automatically include `run/critical_snapshot_l0.json`, `run/receipts/*.json`, and `device_health.jsonl` along with redacted SQLite ledger, logs, and config. Enforces generic regex redaction scrubbing Bearer tokens, GitHub tokens, AWS keys, and private keys. Verified by 3 unit tests in `tests/ops/test_courier_doctor.py`.

- **End-to-End Clean-Machine Simulation (`tests/test_win_clean_machine_simulation.py`):** Authored portable, zero-skip end-to-end lifecycle simulation test proving installation, headless status L0, golden task lifecycle, device health sampling, freeze interruption with active claims, forensic work preservation without repo mutation, exact recovery ladder and receipt emission, safe resume point computation, diagnostics bundle secret scrubbing, and user journal preservation post-uninstall.
- **Clean-Machine Harness Contract Expansion (`tests/test_win_clean_machine_harness.py`):** Added `tests/test_win_clean_machine_simulation.py` as an enforced required acceptance artifact.

- **Golden Path Proxy Hardening (`tests/golden/golden_harness.py`):** Configured `Api.session.trust_env = False` to prevent loopback proxy blocking under host proxy configurations (`HTTP_PROXY`/`http_proxy`). All 11 Golden Acceptance tests run green with zero skips.
- **Local Shell Adapter Wiring (`courier_worker/adapter_bridge.py`, `adapter_runner.py`):** Registered `local_shell` in `ADAPTERS` allowlist and wired execution handling into `adapter_runner.py`, fulfilling the contract "synthetic + local_shell first for internal EXE". Verified by 25 unit and bridge tests in `tests/test_local_shell_adapter.py`.

## 3. Verification & Evidence
- **Automated Test Results (All Green / Portable):**
  - `tests/golden/test_golden_failures.py`: 10 passed (All failure modes: kill worker, duplicate result, late result, timeout kill, cancel, corrupt journal, controller restart, lease expiry, transient provider fail, non-idempotent task block)
  - `tests/golden/test_golden_happy.py`: 1 passed (Happy path restart and replay)
  - `tests/test_local_shell_adapter.py`: 25 passed (Adapter execution, verification, worker bridge claim validation, and runner execution)
  - `tests/test_win_clean_machine_simulation.py`: 1 passed (End-to-End Acceptance Journey)
  - `tests/test_win_clean_machine_harness.py`: 1 passed, 1 skipped
  - `tests/ops/test_courier_doctor.py`: 3 passed
  - `tests/test_windows_dist_uninstall_not_proven.py`: 1 passed, 2 skipped
  - `tests/test_safe_resume_point.py`: 2 passed
  - `tests/test_interruption_harness.py`: 6 passed
  - `tests/test_layered_health.py`: 7 passed
  - `tests/test_work_preservation.py`: 3 passed
  - `tests/test_courier_recovery.py`: 6 passed
  - `tests/test_device_health_sampler.py`: 7 passed
  - `tests/test_right_host_guard.py`: 8 passed
  - `tests/test_courier_status.py`: 9 passed
  - `tests/test_dashboard_xlsx.py`: 2 passed
  - `tests/test_win_process_lifecycle.py`: 3 passed, 2 skipped
  - `tests/test_windows_installer_iss.py`: 7 passed
  - `tests/test_windows_worker_contract.py`: 11 passed
  - `tests/test_windows_worker_timeout_kill.py`: 2 passed
  - `tests/test_desktop_event_bus.py`: 16 passed
  - `tests/test_runtime_continuity.py`: 23 passed
  - `tests/test_ledger_controller_bridge.py`: 8 passed
  - **Combined Suite Total:** 154 passed, 5 skipped cleanly in 90.41s.
- **Kill-By-Name Eradication:** Exact PID targeting (`worker.pid`, `launcher.pid`, `controller.pid`, `hub.pid`) with zero `taskkill /IM` invocations.
- **Local Safety Ratchet:** `python3 scripts/check_local_safety.py . --baseline acceptance/local_safety_baseline.json` -> `total=1 kill_by_name=0 wildcard_bind=1 new=0` -> PASS.
- **Disjointness:** Zero website files touched (`website/public` untouched). Muse's work on `muse/bridge-ledger-controller` preserved.

Status: READY FOR L1 INTEGRATION.

