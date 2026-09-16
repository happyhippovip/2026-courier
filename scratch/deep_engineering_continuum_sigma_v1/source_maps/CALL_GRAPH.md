# COURIER PRODUCTION SOURCE CALL GRAPH & MAP

Generated: 2026-09-10T03:53:21.533Z
Files Audited: 37

## 1. Audited Modules

| Module Path | Lines | Bytes | Classes | Key Functions |
|:---|:---:|:---:|:---|:---|
| `supervisor/audit_ledger.js` | 116 | 3080 | AuditLedger | constructor, getEvents, getEventsForTask, getEventsForProcess |
| `supervisor/chief_envelope.js` | 67 | 1701 | ChiefEscalationEnvelope | - |
| `supervisor/decision_engine.js` | 79 | 2578 | DecisionEngine | constructor |
| `supervisor/diagnostic_bundle.js` | 104 | 3888 | DiagnosticBundleManager | constructor, getBundle |
| `supervisor/index.js` | 77 | 2692 | SupervisorPlane | constructor, getSafetyInvariants |
| `supervisor/lease_manager.js` | 232 | 7077 | ProcessLeaseManager | constructor, _load, _persist, computeProcessFingerprint, computeCommandFingerprint |
| `supervisor/no_stacking.js` | 65 | 2208 | NoStackingDetector | constructor, computeTaskWorkSignature |
| `supervisor/progress_tracker.js` | 116 | 3674 | ProgressTracker | constructor, _load, getEvidenceForProcess, getLatestProgressForProcess |
| `supervisor/reconciliation.js` | 153 | 5880 | RestartReconciler | constructor |
| `supervisor/resource_governor.js` | 162 | 5883 | MachineResourceGovernor | constructor, _initializeDefaultStates, getMachineState, findHealthyRerouteTarget |
| `supervisor/screenshot_spec.js` | 123 | 3450 | ScreenshotSpec | - |
| `supervisor/stall_policy.js` | 181 | 7222 | StallPolicy | constructor |
| `supervisor/task_hygiene.js` | 120 | 3711 | TaskHygiene | constructor, runTaskHygiene |
| `supervisor/types.js` | 100 | 2677 | - | - |
| `money_factory/anti_loop_policy.js` | 204 | 6823 | AntiLoopPolicy | validateAccountAction |
| `money_factory/cheapest_test.js` | 85 | 3545 | CheapestTestSelector | selectCheapestTestForOpportunity, generateTestProposal |
| `money_factory/cycle_ledger.js` | 183 | 6221 | CycleLedger | constructor, _load, _persist, generateFingerprint, validateCycleCompleteness |
| `money_factory/evidence_ledger.js` | 209 | 7515 | EvidenceLedger, strictly | constructor, _load, computeFingerprint, getEvidenceForOpportunity, hasVerifiedSignal |
| `money_factory/first_5_euro_simulator.js` | 185 | 6623 | First5EuroSimulator | simulateEndToEndFlow |
| `money_factory/index.js` | 87 | 2739 | MoneyFactory | constructor, _initializeSeedsIfEmpty, refreshLeaderboard, getWarehouse, getCycleLedger |
| `money_factory/leaderboard_generator.js` | 92 | 4143 | LeaderboardGenerator | generateMarkdown |
| `money_factory/portfolios.js` | 157 | 5206 | PortfolioManager | constructor, getWeights, suggestCategory, rankByHorizon, rankAllHorizons |
| `money_factory/prediction_calibration.js` | 248 | 8515 | PredictionCalibrator | constructor, _load, _persist, recordPrediction, recordActualOutcome |
| `money_factory/safety_gates.js` | 159 | 5244 | SafetyGateManager | getInvariants, checkOperation, executeSpend, executeTrade, signWithWallet |
| `money_factory/scoring.js` | 85 | 3720 | MoneyScorer | computeSpeedMultiplier, parseNumeric, computeScore |
| `money_factory/seed_classes.js` | 294 | 10033 | - | - |
| `money_factory/supervisor_compat.js` | 90 | 2537 | SupervisorCompatibility | bindProcessLease |
| `money_factory/warehouse.js` | 364 | 11959 | OpportunityWarehouse | stringifyYaml, stringifyYamlItem, constructor, _load, _persist |
| `chief/cli.py` | 219 | 8587 | - | cmd_ingest, cmd_delta, cmd_dispatch, cmd_status, cmd_watch |
| `chief/control_plane.py` | 606 | 26009 | ControlPlane | __init__, get_connection, init_db, record_handoff, upsert_finding |
| `chief/coordinator.py` | 257 | 10055 | ChiefCoordinator | __init__, acquire_resource, release_resource, prepare_dispatch, execute_local_headless_dispatch |
| `chief/delta_engine.py` | 204 | 8876 | ChiefDeltaEngine | __init__, compute_delta, generate_delta_markdown, export_reports |
| `chief/ingestor.py` | 298 | 11631 | ChiefIngestor | __init__, compute_sha256, ingest_file, _extract_findings, _extract_patches |
| `chief/safewrite.py` | 95 | 3036 | - | safe_write_text, safe_write_json |
| `chief/types.py` | 163 | 4329 | Lane, Host, TaskStatus, FindingStatus, FindingSeverity, PatchStatus, AuthorityTier, TwoLevelDone, IngestedHandoff, RegisteredFinding, RegisteredPatch, DispatchEnvelope | from_str, from_str, validate_invariants |
| `chief/validator.py` | 89 | 3717 | IngestionValidationError, HandoffValidator | validate_handoff_payload |
| `chief/__init__.py` | 25 | 519 | - | - |

## 2. Evaluation of Omega Findings Against Current Source

| Claim ID | File & Lines | Omega Claim | Classification | Evidence |
|:---|:---|:---|:---:|:---|
| **CX-SIGMA-AUDIT-001** | `supervisor/decision_engine.js:42-43` | Decision engine stall bypass due to telemetry drop | **CONFIRMED_IN_CURRENT_SOURCE** | stallPolicy.evaluateProcessState is invoked with hardcoded hasActiveSubprocesses: false and cpuActivityDetected: false |
| **CX-SIGMA-AUDIT-002** | `supervisor/no_stacking.js:31-32` | Path-only writer collision between different task IDs | **CONFIRMED_IN_CURRENT_SOURCE** | Loop checks exclusively lease.task_id === task_id, omitting working path, resource locks, or file tree boundaries |
| **CX-SIGMA-AUDIT-003** | `money_factory/safety_gates.js:21-58` | Capability lattice absence in safety interceptor | **CONFIRMED_IN_CURRENT_SOURCE** | SafetyGateManager uses a flat list of 14 string literals; operations outside this set bypass interceptor with allowed: true |
| **CX-SIGMA-AUDIT-004** | `supervisor/reconciliation.js:43-79` | Wrapper process orphaning and single-PID tracking | **CONFIRMED_IN_CURRENT_SOURCE** | livePids.includes(lease.pid) only tests the registered wrapper PID, losing track of active grandchild worker processes on Windows |
| **CX-SIGMA-AUDIT-005** | `chief/coordinator.py:212-237` | TOCTOU dispatch race in coordinator execution | **CONFIRMED_IN_CURRENT_SOURCE** | execute_local_headless_dispatch inspects pending dispatches but only marks dispatched AFTER 120s subprocess completes |
