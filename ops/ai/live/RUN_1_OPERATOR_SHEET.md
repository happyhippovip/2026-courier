# RUN_1 Operator Sheet

## 1. Commands
- **Primary Execution Command:** `python3 -m src.main run --id run_001`
- **Secondary Monitors:** `python3 -m ops.monitor --target run_001`
- **Emergency Halt:** `python3 -m ops.halt --target run_001`
- *Note:* Do not execute physically. This is for preparation only.

## 2. Environment
- `COURIER_ENV=production`
- `COURIER_RUN_ID=run_001`
- `COURIER_MAX_HEAVY_JOBS=1`
- `PYTHONPATH=$(pwd)`
- **Base Dir:** `runs/run_001/`

## 3. Process Ownership
- Main PID and PGID must be registered via `ProcessOwnershipManager`.
- Expected Foreign Processes: None. Any foreign process detected via `detect_foreign_processes` should trigger an alert.
- Maximum Timeout: 3600 seconds.
- Orphan handling: Track PGID 1 assignments if detached.

## 4. State Dirs
- **Path:** `runs/run_001/state/`
- Expected Output: `central_state.json`, `.locks/`, `wall/`
- Synchronization: State must be synced at intervals without collision.

## 5. Logs
- **Path:** `runs/run_001/logs/`
- Expected Output:
  - `system.log` (General stdout/stderr)
  - `admission.log` (Resource Admission decisions and quota checks)
  - `ownership.log` (Process tree and timeout monitoring)

## 6. Artifacts
- **Path:** `runs/run_001/artifacts/`
- Expected Output:
  - `run_manifest.json` (contains Runtime Binding metrics)
  - Diagnostic dumps
  - Final results output

## 7. Preflight
- [ ] Ensure CPU <= 80% and RAM <= 4096MB requested limits can be met.
- [ ] Check `MAX_HEAVY_JOBS` is strictly 0 prior to launch.
- [ ] Verify Fingerprint Slots (`FINAL_SHA_PLACEHOLDER_*`) from `binding.py`.
- [ ] Confirm state/log/artifact/temp directories are fully isolated and initialized via `RunIsolation`.

## 8. Cleanup
- Fetch list of all owned processes via `plan_owned_cleanup()`.
- Wait for graceful shutdown signal propagation.
- Flag orphaned processes via `plan_orphan_handling()` if PGID becomes 1.
- Release `heavy_jobs` resource back to `ResourceAdmissionController`.
- Flush all `temp/` paths.

## 9. Evidence Refs
- **Preflight Evidence:** `ops/ai/live/EVIDENCE_BATCH_02.json`
- **Binding State:** `MAC01_BINDING.md` / `MUSE_MAC_03_BINDING.md`
- **Artifact Run Manifest:** `runs/run_001/artifacts/run_manifest.json`

## 10. PASS/FAIL Rules
- **PASS:**
  - Execution completes within the 3600s timeout window.
  - Resource limits (CPU/RAM/Swap) are not breached.
  - `MAX_HEAVY_JOBS=1` rule is strictly maintained throughout the lifecycle.
  - Clean detachment and cleanup of all owned PIDs.
- **FAIL:**
  - Resource Admission rejects the job.
  - Owned processes hit the timeout limit.
  - Undetected/unhandled orphaned processes remain.
  - Missing state snapshot or missing logs in the designated directories.
