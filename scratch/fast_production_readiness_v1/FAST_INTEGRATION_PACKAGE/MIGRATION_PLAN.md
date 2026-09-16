# COURIER PRODUCTION MIGRATION PLAN (ZERO-DOWNTIME ROLLOUT)

## 1. Pre-Flight Verification Checklist
Before applying the integration package to production Courier:
1. Verify git working directory status:
   `git status --porcelain`
2. Verify no active Courier processes are running:
   `Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*courier*" }`
3. Verify zero active writer leases in the system.

## 2. Execution Protocol
Run the unified integration command documented in `EXACT_NEXT_INTEGRATION_COMMAND.md`.
The command performs the following atomic operations:
1. Creates a local timestamped backup of the current `courier/supervisor/` directory in `courier/supervisor_backup_<TIMESTAMP>/`.
2. Copies the runtime dependency directories (`governance/` and `core/`) into `courier/supervisor/`.
3. Copies the enhanced supervisor modules (`no_stacking.js`, `lease_manager.js`, `decision_engine.js`, `progress_tracker.js`, `index.js`) into `courier/supervisor/`.
4. Executes the full 64-test validation suite in-place against production.
5. If tests pass 100%, the backup directory is safely archived. If any test fails, it immediately restores the backup.

## 3. Post-Migration Verification
Execute both test suites against production:
- `node tests/test_supervisor_plane_p0.js` (45 tests)
- `node scratch/fast_production_readiness_v1/tests/test_mandatory_scenarios_suite.js` (19 tests)

Confirm output:
`RESULTS: 64 PASSED | 0 FAILED | 0 ERRORS`
