# FINAL INTEGRATION SEQUENCE (DRY RUN) — POST-FREEZE MAC COURIER

This document defines the exact, non-destructive, stage-by-stage sequence for integrating Windows-certified packages into Mac Courier AFTER active Mac processes are safely frozen:

### STAGE 1: Core Lifecycle Foundation
- **Package**: `PKG-001` (Task Stamp) + `PKG-013` (Logical Identity)
- **Precondition**: Mac Courier idle; active tasks = 0.
- **Verification**: Run `tests/test_stamp_immutability.js`.
- **Rollback Trigger**: Any mutation allowed post-stamp.
- **Rollback Action**: `git checkout -- src/task_stamp.js`.

### STAGE 2: Leases & Scope Concurrency
- **Package**: `PKG-002` (Worker Lease) + `PKG-003` (Process Lease) + `PKG-004` (No-Stacking)
- **Precondition**: Stage 1 PASS.
- **Verification**: Run writer collision and PID reuse tests.
- **Rollback Trigger**: Duplicate writer admitted.
- **Rollback Action**: Restore prior lease manager.

### STAGE 3: Border Guard & Outbound Customs
- **Package**: `PKG-006` (Border Guard) + `PKG-019` (Human Gate Scoping)
- **Precondition**: Stage 2 PASS.
- **Verification**: Verify spend, egress, and TOCTOU blocks.
- **Rollback Trigger**: Undeclared egress permitted.
- **Rollback Action**: Revert to strict fail-closed boundary.

### STAGE 4: Result Customs & Terminal Satisfaction
- **Package**: `PKG-007` (Result Customs) + `PKG-012` (Terminal Satisfaction)
- **Precondition**: Stage 3 PASS.
- **Verification**: Verify narrative rejection and deterministic pass requirement.
- **Rollback Trigger**: Empty queue claims success.
- **Rollback Action**: Revert customs to fail-closed quarantine.

### STAGE 5: Recovery, Telemetry & Money Factory Domain Logic
- **Package**: `PKG-008` (Crash Reconciler) + `PKG-009` (Uncertainty) + `PKG-010` (Governor) + `PKG-018` (Money Factory Adapter)
- **Precondition**: Stage 4 PASS.
- **Verification**: Verify crash cut-points, thermal decoupling, and zero real spend.
- **Rollback Trigger**: Cross-machine throttle or uncertain redispatch.
- **Rollback Action**: Revert to manual recovery triage.
