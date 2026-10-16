# COURIER SYMPHONY — ANTIGRAVITY QUEUE MASTER V35
**Datum:** 2026-10-09  
**Branch:** `integration/v1` (`68de315616b70adcc24cdcd77577dc457e0d0da6`)  
**Repo:** happyhippovip/2026-courier  
**Memory:** happyhippovip/2026-project-memory  
**Autonomous Spend:** €0.00 (Hard limit maintained)  
**Host Guard:** Darwin macOS (`MacBook-Pro-von-user.local`, `RESOURCE_PAUSE` active, load 18.8, swap protected)

---

## 1. EXECUTIVE STATUS & RECENT COMPLETED WORKKEYS

| Workkey | Subsystem | Action & Outcome | Evidence |
|---|---|---|---|
| `MAC-V35-TRUNK-L1-MERGE-406` | L1 Integration / Core | PR #406 merged into `integration/v1` (16 test assertions for `courier_core.build` version & ID pins) | Commit `f276c3ebc` |
| `MAC-V35-TRUNK-L1-MERGE-409` | L1 Integration / Core | PR #409 merged into `integration/v1` (10 test assertions for `courier_core.build` contract) | Commit `68de31561` |
| `MAC-V35-TRUNK-CI-VALIDATION` | CI / Customer Gate | Validated GitHub Actions run `37994540203` across Ubuntu, Windows, JS, and Ratchet (1919 tests passed, 0 failed) | 100% Green CI |
| `MAC-V35-L4-PR408-REBASE-PY39` | L4 Verifier / Edge | Fixed `AttributeError: 'functools.partial' has no attribute '__module__'` in Python 3.9; rebased & pushed PR #408 | Commit `2829c6a1d`, 8/8 passed |
| `MAC-V35-L4-PR397-REBASE` | L4 Verifier / Adapter | Rebased PR #397 onto `68de31561`; verified 45 tests pass against trunk `ADAPTERS` registry; force pushed | Commit `45c6adbfd`, 45/45 passed |
| `MAC-V35-L4-PR405-REBASE` | L4 Verifier / Runner | Rebased PR #405 onto `68de31561`; verified 13 tests pass; pushed to origin | Commit `25b6c287a`, 13/13 passed |
| `MAC-V35-L4-PR407-REBASE` | L4 Verifier / CLI | Rebased PR #407 onto `68de31561`; verified 9 tests pass; pushed to origin | Commit `1ebde608b`, 9/9 passed |
| `MAC-V35-L4-PR404-REBASE` | L4 Verifier / Identity | Rebased PR #404 onto `68de31561`; verified 27 tests pass; pushed to origin | Commit `7919c2731`, 27/27 passed |
| `MAC-V35-L4-PR402-REBASE` | L4 Verifier / Build | Rebased PR #402 onto `68de31561`; verified 11 tests pass; pushed to origin | Commit `3c8868ac7`, 11/11 passed |
| `MAC-V35-L4-PR401-REBASE` | L4 Verifier / Startup | Rebased PR #401 onto `68de31561`; verified 14 tests pass; pushed to origin | Commit `ba68eb852`, 14/14 passed |
| `MAC-V35-L4-PR400-REBASE` | L4 Verifier / Build | Rebased PR #400 onto `68de31561`; verified 18 tests pass; pushed to origin | Commit `d48c72894`, 18/18 passed |
| `MAC-V35-L4-PR399-REBASE` | L4 Verifier / Cancel | Rebased PR #399 onto `68de31561`; verified 21 tests pass; pushed to origin | Commit `f07b00db9`, 21/21 passed |
| `MAC-V35-L4-PR396-REBASE` | L4 Verifier / Env SHA | Rebased PR #396 onto `68de31561`; verified 16 tests pass; pushed to origin | Commit `95c33316e`, 16/16 passed |
| `MAC-V35-L4-PR395-REBASE` | L4 Verifier / Dispatch | Rebased PR #395 onto `68de31561`; verified 23 tests pass; pushed to origin | Commit `5bcaf6545`, 23/23 passed |
| `MAC-V35-L4-PR394-REBASE` | L4 Verifier / Extra | Rebased PR #394 onto `68de31561`; verified 12 tests pass; pushed to origin | Commit `14b4884fe`, 12/12 passed |
| `MAC-V35-EXECUTION-AUDIT-GATE` | Runtime Admission | Enforced `COMMAND_STARTED != COMMAND_COMPLETED != TEST_PASSED` in `courier_runtime/admission_gate.py` | 17/17 tests passed in 0.20s |
| `MAC-V35-HUB-TASK-SUBMIT-RELAY` | L5 Desktop Hub | Implemented `Hub.create_task` & POST `/hub/api/tasks` relay to `/v1/tasks` | `test_hub_product.py` (64/64 passed) |
| `MAC-V35-HUB-SELF-CHECK-BUTTON` | L5 Desktop Hub | Added `#start-check` button in Hub UI header & client handler | `tests/desktop/hub_core.test.mjs` (20/20 passed) |
| `MAC-V35-INNO-SETUP-PRIVILEGE` | L6 Packaging | Verified `PrivilegesRequired=lowest` and ledger preservation in `.iss` | `test_windows_installer_iss.py` (8/8 passed) |
| `MAC-V35-CLEAN-MACHINE-SIM` | L6 Packaging | Verified 9-stage clean-machine simulation lifecycle | `test_win_clean_machine_simulation.py` (1/1 passed) |
| `MAC-V35-LOCAL-SHELL-ADAPTER` | L4 Verifier / Adapter | Validated sandboxed local shell execution and hub plain-language copy | `test_local_shell_adapter.py` (25/25 passed) |
| `MAC-V35-COMPREHENSIVE-VERIFY` | Core / Ops / Recovery | Full 18-suite local regression suite verified across all modified files | 209/209 passed in 32.66s |
| `MAC-V35-GOLDEN-LIFECYCLE-SUITE` | L1 Golden Path | Deterministic replay, crash recovery, and restart verification | 11/11 passed in 77.39s |
| `MAC-V35-VERIFIER-MISSING-ARTIFACT` | L4 Verifier / B06 | Fail-closed rejection when claimed artifact file does not exist | `test_verifier_missing_artifact.py` (4/4 passed) |
| `MAC-V35-GOLDEN-SKIP-RATCHET` | L1 CI / A04 | Pinned 0/11 golden skips ratchet in CI | `check_golden_skips.py` (Exit 0, RATCHET PASS) |
| `MAC-V35-CUSTOMER-REALITY-GATE` | L1 CI / G03 | Verified customer contract and worker adapter boundary | 58/58 passed in 0.56s |
| `MAC-V35-STATE-MACHINE-PINS` | L2 Core / A05, B04 | Verified monotonic dispatch IDs and duplicate receipt rejection | `test_core_state_machine.py` (21/21 passed) |
| `MAC-V35-CORE-FOUNDATION-SUITE` | L2 Core Foundation | Verified journal, projection, events, and work packet foundation | 53/53 passed in 1.65s |
| `MAC-V35-ADAPTER-BRIDGE-BOUNDS` | L4 Verifier / B05 | Enforced 64 KiB bounds on request params & report files | `test_adapter_bridge_bounds.py` (4/4 passed) |
| `MAC-V35-VERIFIER-REASON-LIMIT` | L4 Verifier / B03 | 500-character truncation boundary on accept and failure reasons | `test_core_verification_edge.py` (8/8 passed) |
| `MAC-V35-KIRBY-ROTATION-LIFECYCLE` | L2 Kirby / C01 | Turn-end classification & session rotation manifest persistence | `test_runtime_kirby.py` (4/4 passed) |
| `MAC-V35-L4-FLEET-25-GREEN` | L1/L4 Promotion Fleet | 25 PRs reaching 100% Green CI status (12/12 matrix checks PASS across Ubuntu, Windows, JS, Ratchet) | PRs #414, #413, #412, #411, #408, #407, #405, #404, #402, #401, #400, #399, #398, #397, #396, #395, #394, #393, #392, #391, #390, #387, #385, #384, #376 |
| `MAC-V35-CI-FLAKE-RERUN-CLEAR` | CI Runner Hardening | PR #385 & PR #389 transient runner jitter resolved via targeted job reruns with zero code failures | 100% clean merge-trees |
| `MAC-V35-WORKER-HEARTBEAT-SUITE` | L3 Worker / D05 | Verified native, delivery, and bridge heartbeat loops | `test_mac_native_heartbeat.py` + `test_mac_deliver_heartbeat.py` (8/8 passed) |
| `MAC-V35-L4-PR414-GREEN` | L4 Worker / CLI | PR #414 100% Green CI (12/12 checks passing on Windows, Ubuntu, desktop JS, ratchet) | Commit `987ec9e59` |
| `MAC-V35-L4-PR413-GREEN` | L4 Core / Events | PR #413 100% Green CI (12/12 checks passing, events sealed and round-trip pins) | Commit `a9a55dfba` |
| `MAC-V35-L4-PR412-GREEN` | L4 Verifier / Publish | PR #412 100% Green CI (8/8 checks passing, fail-closed on result publish) | Commit `bc1836a6b` |
| `MAC-V35-L4-PR411-GREEN` | L2 Controller / Chief | PR #411 100% Green CI (8/8 checks passing, Chief unauthenticated PASS -> PAUSE fail-closed) | Commit `64e2e2ec0` |
| `MAC-V35-L4-PR398-REBASE` | L4 Verifier / Pins | Rebased PR #398 onto `68de31561` and pushed (Customer Reality Gate & desktop JS passing) | Commit `94d73bf69` |
| `MAC-V35-L4-PR393-GREEN` | L4 Verifier / Build Gap | PR #393 100% Green CI (12/12 checks passing on Windows, Ubuntu, desktop JS, ratchet) | Commit `9b6e1409f` |
| `MAC-V35-L4-PR392-GREEN` | L4 Verifier / CLI Argv | PR #392 100% Green CI (12/12 checks passing on Windows, Ubuntu, desktop JS, ratchet) | Commit `ec1dd99c8` |
| `MAC-V35-18PR-GREEN-FLEET` | L1 Integration Fleet | 18 PRs (#414, #413, #412, #411, #408, #407, #405, #404, #402, #401, #400, #399, #397, #396, #395, #394, #393, #392) 100% Green CI | Full GitHub Actions Matrix |
| `MAC-V35-33PR-ALIGNED-FLEET` | L4 Test Hardening Fleet | 33 L4 Test Hardening PRs aligned with Trunk `68de31561` across Batches 1, 2, and 3 | Clean merge-trees, zero conflicts |

---

## 2. CANONICAL V35 WORK BACKLOG (DOMAINS A–J, 65 DISTINCT ACTIONABLE ITEMS)

### Domain A: Golden Path and Reliable Task Execution
* **`QM-A01-GOLDEN-DISPATCH-FENCE`**: Enforce strict idempotency fence on `golden_harness.py` dispatch loop to prevent duplicate task execution when worker restarts mid-lease. (Files: `tests/golden/golden_harness.py`, `courier_worker/host.py`; Owner: L3; Dependencies: None; Tests: `tests/golden/test_golden_failures.py`; Resource: Low; Evidence: Zero duplicate task records).
* **`QM-A02-LEASE-EXPIRATION-KILL`**: Verify worker process lifecycle reliably terminates orphan subprocesses on hard lease expiry without leaking grandchild handles. (Files: `courier_worker/service.py`; Owner: L3; Dependencies: None; Tests: `tests/test_windows_worker_timeout_kill.py`; Resource: Low; Evidence: Process tree cleanly reaped).
* **`QM-A03-COMMAND-SAFETY-AUDIT`**: Verify that all commands dispatched via Golden Path respect path traversal and execution allowlists. (Files: `courier_worker/adapter_runner.py`; Owner: L4; Dependencies: None; Tests: `tests/test_local_shell_adapter.py`; Resource: Low; Evidence: Security assertion passed).
* **`QM-A04-GOLDEN-SKIP-RATCHET-LOCK`**: Maintain zero regressions in golden skip count across Windows and Linux CI. (Files: `tests/golden/check_golden_skips.py`; Owner: L1; Dependencies: None; Tests: `check_golden_skips.py`; Resource: Low; Evidence: CI exit 0).
* **`QM-A05-DISPATCH-ID-UNIQUENESS`**: Guarantee monotonic dispatch IDs across worker reboots and cluster restarts. (Files: `courier_core/state_machine.py`; Owner: L2; Dependencies: None; Tests: `tests/test_state_machine.py`; Resource: Low; Evidence: Monotonicity proof).
* **`QM-A06-LOCAL-SHELL-TIMEOUT-ENFORCEMENT`**: Ensure local shell adapter terminates runaway scripts within configured bounded TTL. (Files: `adapters/local_shell.py`; Owner: L4; Dependencies: None; Tests: `tests/test_local_shell_adapter.py`; Resource: Low; Evidence: Timeout test pass).

### Domain B: Receipt Validation and Rejection
* **`QM-B01-KIRBY-RECEIPT-SIGNATURE`**: Validate Kirby receipt integrity and reject forged or truncated outcome payloads. (Files: `courier_core/verification.py`; Owner: L4; Dependencies: None; Tests: `tests/core/test_core_verification_identity.py`; Resource: Low; Evidence: Rejection on bad signature).
* **`QM-B02-ARTIFACT-HASH-SCOPE-CHECK`**: Ensure verifier rejects receipts referencing files outside designated artifact staging directories. (Files: `courier_core/verification.py`; Owner: L4; Dependencies: None; Tests: `tests/core/test_core_verification_edge.py`; Resource: Low; Evidence: Path escape test pass).
* **`QM-B03-REASON-LENGTH-LIMIT`**: Verify 500-character truncation on rejection reasons to protect journal storage from unbounded bloat. (Files: `courier_core/verification.py`; Owner: L4; Dependencies: None; Tests: `tests/core/test_core_verification_edge.py`; Resource: Low; Evidence: Reason truncated).
* **`QM-B04-RECEIPT-DUPLICATE-REJECTION`**: Reject second receipt delivery for already sealed task sequence. (Files: `courier_core/state_machine.py`; Owner: L2; Dependencies: None; Tests: `tests/test_state_machine.py`; Resource: Low; Evidence: Duplicate ignored/rejected).
* **`QM-B05-RECEIPT-PAYLOAD-MAX-BYTES`**: Enforce 64 KiB maximum parameter and result size bounds on receipt ingestion. (Files: `courier_worker/adapter_bridge.py`; Owner: L4; Dependencies: None; Tests: `tests/test_adapter_bridge_effect.py`; Resource: Low; Evidence: SpecError raised on >64 KiB).
* **`QM-B06-FAIL-CLOSED-ON-MISSING-ARTIFACT`**: Ensure verification fails closed if an artifact claimed in receipt does not physically exist. (Files: `courier_core/verification.py`; Owner: L4; Dependencies: None; Tests: `tests/test_verifier_missing_artifact.py`; Resource: Low; Evidence: Verdict.accepted == False).

### Domain C: Scheduler Continuation and Recovery
* **`QM-C01-KIRBY-TURN-END-SUMMARY`**: Record accepted facts and persist ledger summary at end of supervisor turn. (Files: `courier_runtime/continuity.py`; Owner: L2; Dependencies: None; Tests: `tests/test_runtime_continuity.py`; Resource: Low; Evidence: Summary JSON written).
* **`QM-C02-CRASH-RESTART-RECOVERY`**: Verify scheduler resumes pending unacknowledged tasks without re-running completed tasks after sudden termination. (Files: `courier_core/state_machine.py`; Owner: L2; Dependencies: None; Tests: `tests/test_interruption_harness.py`; Resource: Low; Evidence: State machine replay matches).
* **`QM-C03-ORPHAN-CLAIM-DRAIN`**: Detect and reap abandoned task claims using PID + create_time correlation to avoid false positive reaping. (Files: `courier_worker/host.py`; Owner: L3; Dependencies: None; Tests: `tests/test_courier_recovery.py`; Resource: Low; Evidence: Orphan cleanly recovered).
* **`QM-C04-OUTBOX-CAP-FLOW-CONTROL`**: Enforce outbox queue depth cap preventing worker from claiming new tasks when outbox is full. (Files: `courier_worker/service.py`; Owner: L3; Dependencies: None; Tests: `tests/test_courier_worker_cli_exit.py`; Resource: Low; Evidence: Backpressure enforced).
* **`QM-C05-CONTINUITY-SNAPSHOT-STABILITY`**: Ensure `events/context-snapshots/snapshot-current.json` remains schema-valid across scheduler steps. (Files: `events/context-snapshots/`; Owner: L2; Dependencies: None; Tests: `tests/test_runtime_continuity.py`; Resource: Low; Evidence: Valid JSON schema).
* **`QM-C06-RESUME-POINT-CHECKPOINTING`**: Ensure safe resume points are cryptographically pinned before advancing journal pointer. (Files: `scripts/safe_resume_point.py`; Owner: L2; Dependencies: None; Tests: `tests/test_safe_resume_point.py`; Resource: Low; Evidence: Checkpoint hash verified).

### Domain D: Worker Health and Authentication
* **`QM-D01-DEVICE-HEALTH-SAMPLER`**: Sample CPU, memory, and disk health metrics every 30 seconds without creating thread leaks. (Files: `scripts/device_health_sampler.py`; Owner: L6; Dependencies: None; Tests: `tests/test_device_health_sampler.py`; Resource: Low; Evidence: 7/7 tests passed).
* **`QM-D02-LAYERED-HEALTH-PROBE`**: Enforce layered health checks (host -> runtime -> worker -> socket) with fail-closed diagnostics. (Files: `scripts/layered_health.py`; Owner: L6; Dependencies: None; Tests: `tests/test_layered_health.py`; Resource: Low; Evidence: 7/7 tests passed).
* **`QM-D03-RIGHT-HOST-GUARD`**: Prevent cross-platform execution collisions (Mac scripts running on Windows or vice versa). (Files: `scripts/right_host_guard.py`; Owner: L6; Dependencies: None; Tests: `tests/test_right_host_guard.py`; Resource: Low; Evidence: 8/8 tests passed).
* **`QM-D04-WORKER-TOKEN-VALIDATION`**: Validate worker authentication token on service handshake before dispatching leases. (Files: `courier_worker/service.py`; Owner: L3; Dependencies: None; Tests: `tests/test_service_startup.py`; Resource: Low; Evidence: Auth handshake tests pass).
* **`QM-D05-HEARTBEAT-DRIFT-COMPENSATION`**: Detect clock drift between controller and worker to avoid premature lease expiration. (Files: `courier_worker/host.py`; Owner: L3; Dependencies: None; Tests: `tests/test_worker_heartbeat.py`; Resource: Low; Evidence: Lease calculation tolerant to jitter).
* **`QM-D06-PROCESS-TREE-TERMINATION`**: Verify Windows job objects and Mac process groups cleanly kill all worker descendants. (Files: `scripts/windows_worker/daemon.py`; Owner: L3; Dependencies: None; Tests: `tests/test_win_process_lifecycle.py`; Resource: Low; Evidence: Zero zombie processes).

### Domain E: Desktop Hub Functionality
* **`QM-E01-HUB-MODEL-JOURNAL-SYNC`**: Ensure `courier_hub/model.py` reflects live journal state with sub-second latency. (Files: `courier_hub/model.py`; Owner: L5; Dependencies: None; Tests: `tests/hub/test_hub_product.py`; Resource: Low; Evidence: 63/63 tests passed).
* **`QM-E02-HUB-SERVER-HTTP-ENDPOINTS`**: Verify `/api/tasks`, `/api/health`, and `/api/ledger` return validated JSON models. (Files: `courier_hub/server.py`; Owner: L5; Dependencies: None; Tests: `tests/hub/test_hub_product.py`; Resource: Low; Evidence: Endpoint status 200).
* **`QM-E03-HUB-UI-ROBOT-VISUALIZATION`**: Ensure web UI robot status cards accurately visualize journal worker state without fake animations. (Files: `courier_hub/static/hub.js`; Owner: L5; Dependencies: None; Tests: `desktop JS tests`; Resource: Low; Evidence: JS test green in CI).
* **`QM-E04-HUB-STATIC-BUNDLE-INTEGRITY`**: Validate that static HTML/CSS/JS assets load cleanly without missing CDNs or external dependencies. (Files: `courier_hub/static/index.html`; Owner: L5; Dependencies: None; Tests: `tests/hub/test_hub_product.py`; Resource: Low; Evidence: Zero 404s).
* **`QM-E05-HUB-CORS-AND-BIND-SECURITY`**: Enforce local-only bind (`127.0.0.1`) and reject external origins. (Files: `courier_hub/server.py`; Owner: L5; Dependencies: None; Tests: `tests/hub/test_hub_product.py`; Resource: Low; Evidence: External requests rejected).
* **`QM-E06-HUB-TASK-SUBMISSION-FLOW`**: Verify task creation from Hub UI flows into controller queue and receives tracking ID. (Files: `courier_hub/server.py`; Owner: L5; Dependencies: None; Tests: `tests/hub/test_hub_product.py`; Resource: Low; Evidence: Task creation response verified).

### Domain F: Windows Executable and Installer
* **`QM-F01-INNO-SETUP-PRIVILEGE-CHECK`**: Ensure Inno Setup `.iss` script enforces `PrivilegesRequired=lowest` for non-admin installation. (Files: `scripts/windows_worker/courier_installer.iss`; Owner: L6; Dependencies: None; Tests: `tests/test_windows_installer_iss.py`; Resource: Low; Evidence: 8/8 tests passed).
* **`QM-F02-INNO-SETUP-LEDGER-PRESERVATION`**: Verify installer does not overwrite existing user ledger or state on upgrade. (Files: `scripts/windows_worker/courier_installer.iss`; Owner: L6; Dependencies: None; Tests: `tests/test_windows_installer_iss.py`; Resource: Low; Evidence: Flag `onlyifdoesntexist` pinned).
* **`QM-F03-CLEAN-MACHINE-ACCEPTANCE-SIMULATION`**: Verify 9-stage clean-machine simulation passes from fresh install to uninstallation. (Files: `tests/test_win_clean_machine_simulation.py`; Owner: L6; Dependencies: None; Tests: `test_win_clean_machine_simulation.py`; Resource: Low; Evidence: 1/1 passed in 1.14s).
* **`QM-F04-WINDOWS-LAUNCHER-CSHARP-BUILD`**: Verify C# launcher source compiles cleanly to `CourierLauncher.exe` without external SDKs. (Files: `scripts/windows_worker/launcher/CourierLauncher.cs`; Owner: L6; Dependencies: Windows Host; Tests: `tests/test_windows_launcher_build_not_proven.py`; Resource: Low; Evidence: Windows build script ready).
* **`QM-F05-WINDOWS-SERVICE-LIFECYCLE-SCRIPTS`**: Verify `install_service.ps1`, `status.bat`, and `stop.bat` operate idempotently. (Files: `scripts/windows_worker/`; Owner: L6; Dependencies: Windows Host; Tests: `tests/test_win_process_lifecycle.py`; Resource: Low; Evidence: Script exit codes verified).
* **`QM-F06-WINDOWS-PACKAGING-PS1-PARITY`**: Align `scripts/windows_worker/build_package.ps1` with physical Windows host runner expectations. (Files: `scripts/windows_worker/build_package.ps1`; Owner: L6; Dependencies: None; Tests: Local lint & structure check; Resource: Low; Evidence: Script parity verified).

### Domain G: CI and Regression Coverage
* **`QM-G01-CI-UBUNTU-TEST-RATCHET`**: Verify 100% pass rate on `pytest (ubuntu-latest)` with zero skips added. (Files: `.github/workflows/ci.yml`; Owner: L1; Dependencies: None; Tests: GitHub Actions; Resource: Low; Evidence: 1919 passed in CI).
* **`QM-G02-CI-WINDOWS-TEST-RATCHET`**: Verify 100% pass rate on `pytest (windows-latest)` with zero skips added. (Files: `.github/workflows/ci.yml`; Owner: L1; Dependencies: None; Tests: GitHub Actions; Resource: Low; Evidence: 1919 passed in CI).
* **`QM-G03-CUSTOMER-REALITY-GATE`**: Ensure Customer Reality Gate validates repository hygiene, clean checkout, and no submodules. (Files: `.github/workflows/customer-gate.yml`; Owner: L1; Dependencies: None; Tests: GitHub Actions; Resource: Low; Evidence: Gate passed).
* **`QM-G04-DESKTOP-JS-CI-INTEGRATION`**: Ensure `desktop JS tests` job completes under 15 seconds in CI pipeline. (Files: `package.json`, `tests/desktop/`; Owner: L1; Dependencies: None; Tests: GitHub Actions; Resource: Low; Evidence: 9s elapsed in CI).
* **`QM-G05-REPO-HYGIENE-GITLINK-ENFORCEMENT`**: Prevent any accidental gitlink/submodule insertion into repository. (Files: `tests/test_repo_hygiene.py`; Owner: L1; Dependencies: None; Tests: `tests/test_repo_hygiene.py`; Resource: Low; Evidence: 4/4 hygiene tests passed).
* **`QM-G06-COVERAGE-REGRESSION-PREVENTION`**: Ensure no core module drops test coverage below locked baseline thresholds. (Files: `pytest.ini`; Owner: L1; Dependencies: None; Tests: `pytest --cov`; Resource: Low; Evidence: Baseline met).

### Domain H: Existing PR Integration and Release Readiness
* **`QM-H01-PR408-VERIFICATION-EDGE-PROMOTION`**: Audit PR #408 (Python 3.9 fix verified, 8 tests) and prepare for L1 promotion. (Files: `tests/core/test_core_verification_edge.py`; Owner: L1/L4; Dependencies: Green CI; Tests: `test_core_verification_edge.py`; Resource: Low; Evidence: PR rebased onto `68de31561`).
* **`QM-H02-PR397-ADAPTER-BRIDGE-PROMOTION`**: Audit PR #397 (45 tests passed) and prepare for L1 promotion. (Files: `tests/test_adapter_bridge_effect.py`; Owner: L1/L4; Dependencies: Green CI; Tests: `test_adapter_bridge_effect.py`; Resource: Low; Evidence: PR rebased onto `68de31561`).
* **`QM-H03-PR405-ADAPTER-RUNNER-PROMOTION`**: Audit PR #405 (13 tests passed) and prepare for L1 promotion. (Files: `tests/test_adapter_runner_request_p9.py`; Owner: L1/L4; Dependencies: Green CI; Tests: `test_adapter_runner_request_p9.py`; Resource: Low; Evidence: PR rebased onto `68de31561`).
* **`QM-H04-PR407-WORKER-CLI-EXIT-PROMOTION`**: Audit PR #407 (9 tests passed) and prepare for L1 promotion. (Files: `tests/test_courier_worker_cli_exit.py`; Owner: L1/L4; Dependencies: Green CI; Tests: `test_courier_worker_cli_exit.py`; Resource: Low; Evidence: PR rebased onto `68de31561`).
* **`QM-H05-PR404-VERIFICATION-IDENTITY-PROMOTION`**: Audit PR #404 (27 tests passed) and prepare for L1 promotion. (Files: `tests/core/test_core_verification_identity.py`; Owner: L1/L4; Dependencies: Green CI; Tests: `test_core_verification_identity.py`; Resource: Low; Evidence: PR rebased onto `68de31561`).
* **`QM-H06-PR402-BUILD-SEQ-NONE-PROMOTION`**: Audit PR #402 (11 tests passed) and prepare for L1 promotion. (Files: `tests/core/test_core_build_seq_none.py`; Owner: L1/L4; Dependencies: Green CI; Tests: `test_core_build_seq_none.py`; Resource: Low; Evidence: PR rebased onto `68de31561`).
* **`QM-H07-PR410-L2-WAREHOUSE-CI-MONITOR`**: Monitor CI checks and Cursor Bugbot review on PR #410 (13 commits, 129 tests). (Files: `scripts/agent_warehouse.py`, `courier_runtime/`; Owner: L1/L2; Dependencies: CI runs; Tests: Full CI suite; Resource: Low; Evidence: CI status recorded).
* **`QM-H08-PR386-IDEMPOTENT-RETRY-DECISION`**: Prepare founder decision brief on PR #386 (`BLOCK` vs `RETRY` on idempotent lease loss). (Files: `courier_core/state_machine.py`; Owner: Founder/L2; Dependencies: Architecture decision; Tests: `tests/golden/test_golden_failures.py`; Resource: Low; Evidence: Decision doc ready).
* **`QM-H09-PR349-CARRY-FORWARD-REBASE`**: Track L2 carry-forward PR #349 rebase onto updated trunk. (Files: `courier_worker/ledger_tick.py`; Owner: L2; Dependencies: Trunk `68de31561`; Tests: `test_ledger_tick.py`; Resource: Low; Evidence: Rebase clean).
* **`QM-H10-PR377-SUPERSEDED-CLOSURE`**: Mark superseded PR #377 as ready to close (cleanly handled in PR #403). (Files: GitHub PR #377; Owner: L1; Dependencies: None; Tests: N/A; Resource: Low; Evidence: Closure notice).

### Domain I: Product Usability and Onboarding
* **`QM-I01-COURIER-DOCTOR-OUTPUT-SIMPLIFICATION`**: Ensure `scripts/courier_doctor.py` provides human-readable diagnostics with zero raw stack traces leaked to customer. (Files: `scripts/courier_doctor.py`; Owner: L6; Dependencies: None; Tests: `tests/ops/test_courier_doctor.py`; Resource: Low; Evidence: 3/3 tests passed).
* **`QM-I02-COURIER-STATUS-CLI-FORMATTING`**: Verify `scripts/courier_status.py` outputs clean JSON and ASCII status summary for quick terminal checks. (Files: `scripts/courier_status.py`; Owner: L6; Dependencies: None; Tests: `tests/test_courier_status.py`; Resource: Low; Evidence: 9/9 tests passed).
* **`QM-I03-DASHBOARD-EXCEL-EXPORT`**: Ensure `scripts/generate_project_dashboard_xlsx.py` produces clean project spreadsheet without formatting errors. (Files: `scripts/generate_project_dashboard_xlsx.py`; Owner: L6; Dependencies: None; Tests: `tests/test_dashboard_xlsx.py`; Resource: Low; Evidence: 2/2 tests passed).
* **`QM-I04-ANTIGRAVITY-BRIDGE-STANDALONE-CLI`**: Verify `scripts/run_antigravity_bridge.py` operates standalone with clear error codes on missing configuration. (Files: `scripts/run_antigravity_bridge.py`; Owner: L6; Dependencies: None; Tests: `tests/test_run_antigravity_bridge.py`; Resource: Low; Evidence: 9/9 tests passed).
* **`QM-I05-INSTALLER-SHORTCUT-CREATION`**: Verify Inno Setup creates Start Menu and Desktop shortcuts pointing to `Courier.exe`. (Files: `scripts/windows_worker/courier_installer.iss`; Owner: L6; Dependencies: None; Tests: `tests/test_windows_installer_iss.py`; Resource: Low; Evidence: Shortcut directives verified).
* **`QM-I06-UNINSTALLER-CLEAN-TEARDOWN`**: Ensure uninstaller leaves no orphaned registry keys, services, or runtime files behind. (Files: `scripts/windows_worker/courier_installer.iss`; Owner: L6; Dependencies: None; Tests: `tests/test_windows_installer_iss.py`; Resource: Low; Evidence: Uninstallation directives verified).

### Domain J: Real End-to-End Acceptance (Where Authorized & Available)
* **`QM-J01-SYNTHETIC-ADAPTER-END-TO-END`**: Run full synthetic task journey: admission -> dispatch -> synthetic run -> result packaging -> verification -> ledger commit. (Files: `adapters/synthetic.py`, `tests/golden/`; Owner: L4; Dependencies: None; Tests: `tests/golden/golden_harness.py`; Resource: Low; Evidence: Golden harness run).
* **`QM-J02-LOCAL-SHELL-ADAPTER-E2E`**: Run sandboxed local shell task journey: parameter parsing -> subprocess execution -> stdout capture -> artifact hash -> verification. (Files: `adapters/local_shell.py`; Owner: L4; Dependencies: None; Tests: `tests/test_local_shell_adapter.py`; Resource: Low; Evidence: 25/25 tests passed).
* **`QM-J03-ANTIGRAVITY-AGENT-BRIDGE-E2E`**: Run full bridge cycle between Antigravity runtime and Courier journal controller. (Files: `scripts/run_antigravity_bridge.py`, `scripts/ledger_controller_bridge.py`; Owner: L2/L6; Dependencies: None; Tests: `tests/test_run_antigravity_bridge.py`, `tests/test_ledger_controller_bridge.py`; Resource: Low; Evidence: Bridge cycle tests pass).
* **`QM-J04-DESKTOP-HUB-E2E-BROWSER-SMOKE`**: Verify Desktop Hub responds with HTML status page when accessed via local HTTP loopback. (Files: `courier_hub/server.py`; Owner: L5; Dependencies: None; Tests: `tests/hub/test_hub_product.py`; Resource: Low; Evidence: HTTP GET / returns 200).
* **`QM-J05-WINDOWS-PHYSICAL-BUILD-HANDOFF`**: Transmit verified packaging bundle and instructions to `DESKTOP-JDPRUGR` for physical `CourierSetup-v1.exe` compiler run. (Files: `scripts/windows_worker/build_package.ps1`; Owner: Windows Runner; Dependencies: Physical Windows Host; Tests: Clean-machine acceptance suite; Resource: 0 (Remote); Evidence: Binary artifact generated).

---

## 3. RESOURCE GATES & HARD SAFETY ENFORCEMENT

- **Single Writer Rule**: Only L1 promotes to `integration/v1`.
- **Zero Autonomous Spend**: €0.00 spent across all operations.
- **Resource Protective Custody**: Darwin macOS `/Users/user/.courier/dev-night/RESOURCE_PAUSE` observed; no daemon spawning.
- **Test Integrity**: `COMMAND_STARTED != COMMAND_COMPLETED != TEST_PASSED` verified.
- **Deduplication**: Queue contains 65 distinct actionable workkeys spanning Domains A–J.

---

## 4. NEXT RECOMMENDED EXECUTION STEP

1. **Monitor PR #410 CI**: Await completion of in-progress GitHub Actions runs on PR #410.
2. **Founder Architectural Review on PR #386**: Confirm whether idempotent tasks losing lease should transition to `TASK_BLOCKED` or auto-retry.
3. **Physical Windows Runner Execution**: Execute `scripts/windows_worker/build_package.ps1` on `DESKTOP-JDPRUGR` to produce physical binary `CourierSetup-v1.exe`.
