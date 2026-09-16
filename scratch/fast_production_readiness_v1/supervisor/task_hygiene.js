// Task Hygiene Engine — Obsolete Process Cleanup & Background Preservation
// Invariant: Do NOT blindly kill by command name alone. Require task ownership/evidence.

const { LEASE_STATUS, EVENT_TYPE } = require('./types');

const KNOWN_HELPER_PATTERNS = [
  /\btail\s+-f\b/i,
  /\bgrep\b.*loop/i,
  /\bwait\b.*loop/i,
  /\blldb\b/i,
  /\bgdb\b/i,
  /\bwatcher\b/i,
  /\bwatchdog\b/i,
  /\btest_watcher\b/i
];

class TaskHygiene {
  constructor(leaseManager, auditLedger = null) {
    if (!leaseManager) throw new Error('[HYGIENE_ERROR] leaseManager is required');
    this.leaseManager = leaseManager;
    this.auditLedger = auditLedger;
  }

  runTaskHygiene(taskId, reason = 'TASK_COMPLETED') {
    if (!taskId) throw new Error('[HYGIENE_ERROR] taskId is required');

    const allLeases = this.leaseManager.getAllLeases();
    const taskLeases = allLeases.filter(l => l.task_id === taskId);

    const terminated = [];
    const retained = [];
    const skippedAlreadyTerminated = [];

    for (const lease of taskLeases) {
      if (lease.status === LEASE_STATUS.COMPLETED || lease.status === LEASE_STATUS.TERMINATED) {
        skippedAlreadyTerminated.push(lease.process_lease_id);
        continue;
      }

      // Check if this is an explicitly preserved background service
      if (lease.cleanup_policy === 'PRESERVE_BACKGROUND') {
        this.leaseManager.updateStatus(
          lease.process_lease_id,
          LEASE_STATUS.WAITING_VALID,
          `Retained background service after task ${taskId} completion`
        );
        retained.push({
          process_lease_id: lease.process_lease_id,
          command: lease.command,
          purpose: lease.purpose,
          reason: 'Explicit PRESERVE_BACKGROUND policy'
        });

        if (this.auditLedger) {
          this.auditLedger.recordEvent({
            task_id: taskId,
            process_lease_id: lease.process_lease_id,
            event_type: EVENT_TYPE.PROCESS_RETAINED,
            reason_codes: ['PRESERVE_BACKGROUND']
          });
        }
        continue;
      }

      // Check if command matches obsolete helper pattern or default task-end cleanup
      const isKnownHelper = KNOWN_HELPER_PATTERNS.some(pat => pat.test(lease.command || ''));
      const shouldTerminate = isKnownHelper || lease.cleanup_policy === 'TERMINATE_ON_TASK_END';

      if (shouldTerminate) {
        this.leaseManager.updateStatus(
          lease.process_lease_id,
          LEASE_STATUS.TERMINATED,
          `Task ${taskId} finished: ${reason}`
        );
        terminated.push({
          process_lease_id: lease.process_lease_id,
          command: lease.command,
          purpose: lease.purpose,
          is_helper: isKnownHelper,
          reason
        });

        if (this.auditLedger) {
          this.auditLedger.recordEvent({
            task_id: taskId,
            process_lease_id: lease.process_lease_id,
            event_type: EVENT_TYPE.PROCESS_TERMINATED,
            reason_codes: ['TASK_HYGIENE_CLEANUP', isKnownHelper ? 'OBSOLETE_HELPER' : 'TASK_END_CLEANUP']
          });
        }
      }
    }

    const summary = {
      task_id: taskId,
      timestamp: new Date().toISOString(),
      terminated_count: terminated.length,
      retained_count: retained.length,
      skipped_count: skippedAlreadyTerminated.length,
      terminated,
      retained
    };

    if (this.auditLedger) {
      this.auditLedger.recordEvent({
        task_id: taskId,
        event_type: EVENT_TYPE.TASK_HYGIENE_COMPLETED,
        reason_codes: [`TERMINATED_${terminated.length}`, `RETAINED_${retained.length}`]
      });
    }

    return summary;
  }
}

module.exports = {
  KNOWN_HELPER_PATTERNS,
  TaskHygiene
};
