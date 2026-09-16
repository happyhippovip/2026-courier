// Crash / Restart Reconciliation Engine
// Invariant: If prior execution MAY have happened without durable proof of effect/non-effect:
// -> EXECUTION_UNCERTAIN
// -> NO redispatch
// -> NO retry
// -> NO duplicate execution

const { LEASE_STATUS, EVENT_TYPE } = require('./types');

class RestartReconciler {
  constructor(leaseManager, auditLedger = null) {
    if (!leaseManager) throw new Error('[RECONCILER_ERROR] leaseManager is required');
    this.leaseManager = leaseManager;
    this.auditLedger = auditLedger;
  }

  reconcile({
    livePids = [], // Array of currently live process PIDs
    liveProcessMap = {}, // Map of pid -> { command, startedAt }
    pendingDispatchTasks = [] // Tasks that may have dispatched before restart
  }) {
    const allLeases = this.leaseManager.getAllLeases();
    const results = {
      reconciled_at: new Date().toISOString(),
      known_live_progressing: [],
      known_live_waiting: [],
      known_completed: [],
      known_missing: [],
      unknown_live_processes: [],
      orphaned_children: [],
      execution_uncertain_tasks: []
    };

    const recognizedPids = new Set();

    // 1. Reconcile known leases
    for (const lease of allLeases) {
      if (lease.status === LEASE_STATUS.COMPLETED || lease.status === LEASE_STATUS.TERMINATED) {
        results.known_completed.push(lease.process_lease_id);
        continue;
      }

      const isPidLive = livePids.includes(lease.pid);

      if (isPidLive) {
        recognizedPids.add(lease.pid);
        // Verify fingerprint if command is inspectable
        const liveInfo = liveProcessMap[lease.pid];
        let fingerprintMatch = true;
        if (liveInfo && liveInfo.command) {
          fingerprintMatch = (liveInfo.command === lease.command);
        }

        if (fingerprintMatch) {
          if (lease.status === LEASE_STATUS.PROGRESSING || lease.status === LEASE_STATUS.RUNNING) {
            results.known_live_progressing.push(lease.process_lease_id);
          } else {
            results.known_live_waiting.push(lease.process_lease_id);
          }
        } else {
          // PID recycled or mismatched
          this.leaseManager.updateStatus(lease.process_lease_id, LEASE_STATUS.STALLED, 'PID recycled by another process');
          results.known_missing.push(lease.process_lease_id);
        }
      } else {
        // Known lease but process has died while restarting
        // If it was supposed to produce a result and none exists, mark uncertain or terminated
        if (lease.expected_completion_condition && !lease.result_reference) {
          this.leaseManager.updateStatus(lease.process_lease_id, LEASE_STATUS.EXECUTION_UNCERTAIN, 'Process disappeared during restart without result proof');
          results.execution_uncertain_tasks.push({
            task_id: lease.task_id,
            process_lease_id: lease.process_lease_id,
            reason: 'Process died during restart without durable proof of outcome'
          });
        } else {
          this.leaseManager.updateStatus(lease.process_lease_id, LEASE_STATUS.TERMINATED, 'Process gone on restart');
          results.known_missing.push(lease.process_lease_id);
        }
      }

      // Check for orphan condition: parent is completed but child is still active
      if (lease.parent_process_id) {
        const parent = this.leaseManager.getLease(lease.parent_process_id);
        if (parent && (parent.status === LEASE_STATUS.COMPLETED || parent.status === LEASE_STATUS.TERMINATED)) {
          if (lease.cleanup_policy !== 'PRESERVE_BACKGROUND') {
            this.leaseManager.updateStatus(lease.process_lease_id, LEASE_STATUS.ORPHANED, `Parent ${lease.parent_process_id} completed`);
            results.orphaned_children.push(lease.process_lease_id);
          }
        }
      }
    }

    // 2. Check for unknown live processes that have no lease
    for (const pid of livePids) {
      if (!recognizedPids.has(pid)) {
        results.unknown_live_processes.push({
          pid,
          info: liveProcessMap[pid] || 'UNATTRIBUTED_PROCESS',
          status: 'UNATTRIBUTED_NEVER_BLINDLY_KILL'
        });
      }
    }

    // 3. Enforce Critical Invariant: Possible previous dispatch without proof
    for (const pending of pendingDispatchTasks) {
      const existingLease = allLeases.find(l => l.task_id === pending.task_id);
      const hasProofOfEffect = pending.hasDurableProofOfEffect === true;
      const hasProofOfNonEffect = pending.hasDurableProofOfNonEffect === true;

      if (!hasProofOfEffect && !hasProofOfNonEffect) {
        // Outcome is completely uncertain!
        results.execution_uncertain_tasks.push({
          task_id: pending.task_id,
          status: LEASE_STATUS.EXECUTION_UNCERTAIN,
          policy: 'BLOCK_REDISPATCH_AND_RETRY',
          reason: 'Dispatched state uncertain without proof of effect or non-effect'
        });

        if (existingLease) {
          this.leaseManager.updateStatus(existingLease.process_lease_id, LEASE_STATUS.EXECUTION_UNCERTAIN, 'Pending task dispatch outcome unproven');
        }

        if (this.auditLedger) {
          this.auditLedger.recordEvent({
            task_id: pending.task_id,
            process_lease_id: existingLease?.process_lease_id || null,
            event_type: EVENT_TYPE.EXECUTION_UNCERTAIN,
            reason_codes: ['UNCERTAIN_DISPATCH_BLOCK_RETRY']
          });
        }
      }
    }

    if (this.auditLedger) {
      this.auditLedger.recordEvent({
        task_id: 'SYSTEM_RESTART',
        event_type: EVENT_TYPE.RESTART_RECONCILIATION,
        reason_codes: [
          `LIVE_${results.known_live_progressing.length}`,
          `UNCERTAIN_${results.execution_uncertain_tasks.length}`,
          `ORPHANS_${results.orphaned_children.length}`
        ]
      });
    }

    return results;
  }
}

module.exports = {
  RestartReconciler
};
