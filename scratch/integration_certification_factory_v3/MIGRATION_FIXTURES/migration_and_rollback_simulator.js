/**
 * MIGRATION & ROLLBACK SIMULATOR
 * 
 * Formal models for Campaigns 035 – 048:
 * - Campaign 035: Legacy State Migration
 * - Campaign 036: In-Flight Task Migration
 * - Campaign 037: Pending Result Migration
 * - Campaign 038: Execution Uncertainty Migration
 * - Campaign 039: Human Gate Migration
 * - Campaign 040: Follow-Ups History Preservation
 * - Campaign 041: Stale Lease Safe Reconcile
 * - Campaign 042: Rollback Baseline & History Preservation
 * - Campaign 043: Rollback after Stamp
 * - Campaign 044: Rollback after Dispatch
 * - Campaign 045: Rollback after Result
 * - Campaign 046: Rollback after Verification
 * - Campaign 047: Border Guard Degraded Mode Rollback (Fail-Closed)
 * - Campaign 048: Supervisor Degraded Mode Rollback (No Auto-Retry)
 */

class MigrationAndRollbackSimulator {
  /**
   * Migrate legacy v1 state to v3 contract
   */
  static migrateState(legacyState) {
    const migrated = {
      state_version: '3.0',
      migrated_at: new Date().toISOString(),
      tasks: []
    };

    for (const t of legacyState.tasks || []) {
      const migratedTask = {
        task_id: t.id || t.task_id,
        task_version: t.version || 1,
        goal_id: t.goal_id || 'DEFAULT_GOAL',
        status: t.status,
        canonical_work_id: t.canonical_id || t.id,
        in_flight: t.status === 'RUNNING' || t.status === 'IN_FLIGHT',
        worker_id: t.assigned_worker || t.worker_id || null,
        human_gate: Boolean(t.human_gate || t.blocked_on_human),
        execution_uncertain: t.status === 'EXECUTION_UNCERTAIN',
        pending_verify: t.status === 'PENDING_VERIFY' || t.status === 'RESULT_RECEIVED',
        follow_ups: t.follow_ups || [],
        history: [...(t.history || []), { event: 'MIGRATED_TO_V3', timestamp: new Date().toISOString() }]
      };

      // Invariants:
      // 1. In-flight task never loses identity or assigned worker
      if (migratedTask.in_flight && !migratedTask.worker_id) {
        migratedTask.status = 'EXECUTION_UNCERTAIN';
        migratedTask.execution_uncertain = true;
      }

      // 2. Execution uncertain remains uncertain (never converted to retryable)
      if (t.status === 'EXECUTION_UNCERTAIN') {
        migratedTask.status = 'EXECUTION_UNCERTAIN';
        migratedTask.retryable = false;
      }

      // 3. Human gate survives migration
      if (t.human_gate) {
        migratedTask.human_gate = true;
        migratedTask.status = 'BLOCKED_ON_HUMAN_GATE';
      }

      migrated.tasks.push(migratedTask);
    }

    return migrated;
  }

  /**
   * Simulate package rollback while preserving history
   */
  static rollbackPackage(currentState, rolledBackPackageId) {
    const rolledBackState = {
      ...currentState,
      state_version: currentState.state_version + '_ROLLED_BACK_' + rolledBackPackageId,
      rollback_history: [
        ...(currentState.rollback_history || []),
        { rolled_back_package: rolledBackPackageId, at: new Date().toISOString() }
      ]
    };

    // If Border Guard (PKG-006) rolled back: must fail closed, NOT open
    if (rolledBackPackageId === 'PKG-006') {
      rolledBackState.degraded_mode = 'BORDER_GUARD_FAIL_CLOSED';
      rolledBackState.allow_dispatches = false; // Degraded safe mode
    }

    // If Supervisor (PKG-008/PKG-009) rolled back: no automatic retries
    if (rolledBackPackageId === 'PKG-008' || rolledBackPackageId === 'PKG-009') {
      rolledBackState.degraded_mode = 'SUPERVISOR_MANUAL_TRIAGE_ONLY';
      rolledBackState.auto_retry_enabled = false;
    }

    return rolledBackState;
  }
}

module.exports = { MigrationAndRollbackSimulator };
