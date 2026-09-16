// Stall Policy — Real Signal Evaluation & Anti-Time-Kill Rules
// Invariants:
// - TIME ALONE MUST NEVER CAUSE TERMINATION.
// - Soft check (300s): CHECK_PROGRESS.
// - Diagnostic threshold (900s): CAPTURE_DIAGNOSTIC_BUNDLE.
// - Stalled does NOT automatically kill.
// - Hung requires verified lack of progress + unresponsive state.

const { LEASE_STATUS, THRESHOLDS, SUPERVISOR_DECISION } = require('./types');

class StallPolicy {
  constructor(customThresholds = null) {
    this.softCheckSeconds = customThresholds?.SOFT_CHECK_AFTER_SECONDS || THRESHOLDS.SOFT_CHECK_AFTER_SECONDS;
    this.diagnosticSeconds = customThresholds?.DIAGNOSTIC_AFTER_SECONDS || THRESHOLDS.DIAGNOSTIC_AFTER_SECONDS;
  }

  evaluateProcessState({
    lease,
    nowMs = Date.now(),
    recentProgressCount = 0,
    hasActiveSubprocesses = false,
    cpuActivityDetected = false,
    isWaitingOnKnownDependency = false,
    hasParentCompleted = false,
    isDuplicateOfActiveCanonical = false,
    isExecutionStateUncertain = false,
    isBlockedByHumanGate = false
  }) {
    if (!lease) {
      return {
        classification: LEASE_STATUS.ORPHANED,
        decision: SUPERVISOR_DECISION.TERMINATE_ORPHAN,
        reason: 'Lease missing or unowned',
        recommended_action: 'TERMINATE_ORPHAN'
      };
    }

    // 1. Human Gate Priority
    if (isBlockedByHumanGate || lease.status === LEASE_STATUS.HUMAN_GATE) {
      return {
        classification: LEASE_STATUS.HUMAN_GATE,
        decision: SUPERVISOR_DECISION.HUMAN_GATE,
        reason: 'Execution paused awaiting explicit human authorization',
        recommended_action: 'HUMAN_GATE'
      };
    }

    // 2. Execution Uncertain Priority (Zero retry, Zero redispatch)
    if (isExecutionStateUncertain || lease.status === LEASE_STATUS.EXECUTION_UNCERTAIN) {
      return {
        classification: LEASE_STATUS.EXECUTION_UNCERTAIN,
        decision: SUPERVISOR_DECISION.BLOCK_EXECUTION_UNCERTAIN,
        reason: 'Execution outcome uncertain; duplicate execution and retry strictly blocked',
        recommended_action: 'BLOCK_EXECUTION_UNCERTAIN'
      };
    }

    // 3. Duplicate Process Priority
    if (isDuplicateOfActiveCanonical || lease.status === LEASE_STATUS.DUPLICATE) {
      return {
        classification: LEASE_STATUS.DUPLICATE,
        decision: SUPERVISOR_DECISION.TERMINATE_DUPLICATE,
        reason: 'Duplicate redundant process detected; preserving canonical active process',
        recommended_action: 'TERMINATE_DUPLICATE'
      };
    }

    // 4. Orphaned Process Priority (Parent completed but child remains unpreserved)
    if (hasParentCompleted && lease.cleanup_policy !== 'PRESERVE_BACKGROUND') {
      return {
        classification: LEASE_STATUS.ORPHANED,
        decision: SUPERVISOR_DECISION.TERMINATE_ORPHAN,
        reason: 'Parent task completed; unpreserved child helper is orphaned',
        recommended_action: 'TERMINATE_ORPHAN'
      };
    }

    // 5. Valid Waiting Process (Network, Worker lease wait, Sleep)
    if (isWaitingOnKnownDependency || lease.status === LEASE_STATUS.WAITING_VALID) {
      return {
        classification: LEASE_STATUS.WAITING_VALID,
        decision: SUPERVISOR_DECISION.WAIT,
        reason: 'Process in valid waiting state for external dependency or worker dispatch',
        recommended_action: 'WAIT'
      };
    }

    // 6. Active Progress (Evidence present or recent progress)
    if (recentProgressCount > 0 || cpuActivityDetected || hasActiveSubprocesses) {
      return {
        classification: LEASE_STATUS.PROGRESSING,
        decision: SUPERVISOR_DECISION.KEEP_RUNNING,
        reason: 'Verifiable progress or CPU/subprocess activity observed',
        recommended_action: 'KEEP_RUNNING'
      };
    }

    // 7. Time elapsed calculation since last heartbeat or progress
    const startedMs = new Date(lease.started_at).getTime();
    const lastProgressMs = lease.last_progress_at ? new Date(lease.last_progress_at).getTime() : startedMs;
    const elapsedSinceProgressSec = Math.max(0, (nowMs - lastProgressMs) / 1000.0);

    // Rule: Quiet process under soft threshold is normal running
    if (elapsedSinceProgressSec < this.softCheckSeconds) {
      return {
        classification: LEASE_STATUS.RUNNING,
        decision: SUPERVISOR_DECISION.KEEP_RUNNING,
        reason: `Process active; elapsed without event (${elapsedSinceProgressSec.toFixed(0)}s) < soft threshold (${this.softCheckSeconds}s)`,
        recommended_action: 'KEEP_RUNNING'
      };
    }

    // Rule: Between soft threshold (300s) and diagnostic threshold (900s) -> CHECK_PROGRESS
    if (elapsedSinceProgressSec >= this.softCheckSeconds && elapsedSinceProgressSec < this.diagnosticSeconds) {
      return {
        classification: LEASE_STATUS.STALLED,
        decision: SUPERVISOR_DECISION.CHECK_PROGRESS,
        reason: `No progress observed for ${elapsedSinceProgressSec.toFixed(0)}s (exceeded soft check ${this.softCheckSeconds}s); diagnosing further. NEVER KILL.`,
        recommended_action: 'CHECK_PROGRESS'
      };
    }

    // Rule: Exceeded diagnostic threshold (900s) -> CAPTURE_DIAGNOSTIC_BUNDLE
    // TIME ALONE MUST NEVER CAUSE TERMINATION.
    return {
      classification: LEASE_STATUS.STALLED,
      decision: SUPERVISOR_DECISION.CAPTURE_DIAGNOSTIC,
      reason: `No progress observed for ${elapsedSinceProgressSec.toFixed(0)}s (exceeded diagnostic threshold ${this.diagnosticSeconds}s); trigger diagnostic bundle capture. Auto-kill forbidden.`,
      recommended_action: 'CAPTURE_DIAGNOSTIC'
    };
  }

  evaluateHungWithEvidence({
    lease,
    diagnosticBundle,
    nowMs = Date.now(),
    cpuUsagePercent = 0.0,
    hasUnresponsivePing = true
  }) {
    // A process can only be classified as HUNG if BOTH diagnostic threshold is reached AND zero activity/unresponsive ping is confirmed
    const startedMs = new Date(lease.started_at).getTime();
    const lastProgressMs = lease.last_progress_at ? new Date(lease.last_progress_at).getTime() : startedMs;
    const elapsedSec = (nowMs - lastProgressMs) / 1000.0;

    if (elapsedSec < this.diagnosticSeconds) {
      return {
        classification: LEASE_STATUS.STALLED,
        decision: SUPERVISOR_DECISION.CHECK_PROGRESS,
        reason: 'Cannot classify as HUNG before diagnostic threshold is reached'
      };
    }

    if (!diagnosticBundle) {
      return {
        classification: LEASE_STATUS.STALLED,
        decision: SUPERVISOR_DECISION.CAPTURE_DIAGNOSTIC,
        reason: 'Cannot classify as HUNG without diagnostic bundle evidence'
      };
    }

    if (cpuUsagePercent === 0.0 && hasUnresponsivePing) {
      return {
        classification: LEASE_STATUS.HUNG,
        decision: SUPERVISOR_DECISION.TERMINATE_HUNG,
        reason: `HUNG verified with evidence: 0% CPU, unresponsive ping, no progress for ${elapsedSec.toFixed(0)}s, diagnostic bundle ${diagnosticBundle.diagnostic_id}`,
        recommended_action: 'TERMINATE_HUNG'
      };
    }

    return {
      classification: LEASE_STATUS.STALLED,
      decision: SUPERVISOR_DECISION.WAIT,
      reason: 'Low activity but ping or residual CPU detected; preserve process pending further observation'
    };
  }
}

module.exports = {
  StallPolicy
};
