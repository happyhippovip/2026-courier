// Supervisor Decision Engine — Deterministic Runtime State Evaluation
// Invariant: This engine supervises runtime execution. It must NEVER become a second planner/orchestrator.

const { LEASE_STATUS, SUPERVISOR_DECISION } = require('./types');
const { StallPolicy } = require('./stall_policy');

class DecisionEngine {
  constructor(stallPolicy = null) {
    this.stallPolicy = stallPolicy || new StallPolicy();
  }

  evaluate({
    lease,
    progressEvidence = [],
    parentState = null,
    resourceState = 'NORMAL',
    diagnosticBundle = null,
    isExecutionStateUncertain = false,
    isBlockedByHumanGate = false,
    isDuplicate = false,
    nowMs = Date.now()
  }) {
    if (!lease) {
      return {
        classification: LEASE_STATUS.ORPHANED,
        decision: SUPERVISOR_DECISION.TERMINATE_ORPHAN,
        reason_codes: ['MISSING_LEASE'],
        evidence_refs: [],
        confidence: 1.0,
        recommended_action: SUPERVISOR_DECISION.TERMINATE_ORPHAN
      };
    }

    const hasParentCompleted = parentState && (parentState.status === 'DONE' || parentState.status === 'COMPLETED');
    const recentEvCount = progressEvidence.length;

    // Use StallPolicy for base classification
    const evalResult = this.stallPolicy.evaluateProcessState({
      lease,
      nowMs,
      recentProgressCount: recentEvCount,
      hasActiveSubprocesses: false,
      cpuActivityDetected: false,
      isWaitingOnKnownDependency: lease.status === LEASE_STATUS.WAITING_VALID,
      hasParentCompleted,
      isDuplicateOfActiveCanonical: isDuplicate,
      isExecutionStateUncertain,
      isBlockedByHumanGate
    });

    const evidenceRefs = progressEvidence.map(e => e.evidence_id || e.fingerprint);
    if (diagnosticBundle) {
      evidenceRefs.push(diagnosticBundle.diagnostic_id);
    }

    // Confidence assignment
    let confidence = 0.8;
    if (evalResult.classification === LEASE_STATUS.PROGRESSING) confidence = 0.95;
    if (evalResult.classification === LEASE_STATUS.EXECUTION_UNCERTAIN) confidence = 1.0;
    if (evalResult.classification === LEASE_STATUS.HUMAN_GATE) confidence = 1.0;
    if (evalResult.classification === LEASE_STATUS.ORPHANED) confidence = 0.9;

    return {
      process_lease_id: lease.process_lease_id,
      task_id: lease.task_id,
      classification: evalResult.classification,
      decision: evalResult.decision,
      reason_codes: [evalResult.reason],
      evidence_refs: evidenceRefs,
      confidence,
      recommended_action: evalResult.recommended_action
    };
  }
}

module.exports = {
  DecisionEngine
};
