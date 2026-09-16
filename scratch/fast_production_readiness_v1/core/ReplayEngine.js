// Replay Engine & Crash Reconciler
const { StateProjector } = require('./StateProjector');

class ReplayEngine {
  static rebuildState(eventLog) {
    const { validEntries, tornEntries } = eventLog.recoverAndReplay();
    const projector = new StateProjector();
    const snapshot = projector.projectAll(validEntries);
    return {
      snapshot,
      total_events: validEntries.length,
      torn_entries: tornEntries,
      projector
    };
  }
}

class CrashReconciler {
  static reconcileOnStartup(rebuiltSnapshot) {
    const actions = [];
    
    // Rule 1: Leases from previous dead processes must be purged
    const reconciledLeases = [];
    for (const lease of rebuiltSnapshot.active_leases) {
      actions.push({ action: 'PURGE_STALE_CRASH_LEASE', resource: lease.resource, taskId: lease.taskId });
    }
    
    // Rule 2: Tasks marked IN_FLIGHT or DISPATCHED without result envelope become EXECUTION_UNCERTAIN
    const reconciledTasks = rebuiltSnapshot.tasks.map(t => {
      if (t.state === 'DISPATCHED' || t.state === 'IN_FLIGHT') {
        actions.push({ action: 'FENCE_UNCERTAIN_TASK', taskId: t.task_id });
        return { ...t, state: 'EXECUTION_UNCERTAIN', uncertainty_reason: 'CRASH_MID_EXECUTION' };
      }
      return t;
    });

    return {
      reconciledTasks,
      reconciledLeases,
      actionsTaken: actions
    };
  }
}

module.exports = {
  ReplayEngine,
  CrashReconciler
};
