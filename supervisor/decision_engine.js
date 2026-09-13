// Supervisor Decision Engine — Deterministic Runtime State Evaluation
// Integrates Authoritative BorderGuard (GAP-004) and Completion Governor (GAP-003)
// Invariants:
// 1. This engine supervises runtime execution. It must NEVER become a second planner/orchestrator.
// 2. Authoritative BorderGuard check must occur immediately before any dispatch.
// 3. Workers possess ZERO global completion authority; only CompletionGovernor may evaluate mission status.

const { LEASE_STATUS, SUPERVISOR_DECISION } = require('./types');
const { StallPolicy } = require('./stall_policy');
const { BorderGuard } = require('../governance/BorderGuard');
const { TaskPassport } = require('../governance/TaskPassport');
const { CompletionGovernor } = require('../governance/CompletionGovernor');

class DecisionEngine {
  constructor(stallPolicy = null, lockManager = null) {
    this.stallPolicy = stallPolicy || new StallPolicy();
    this.lockManager = lockManager;
    this.completionGovernor = new CompletionGovernor();
  }

  // Pre-Dispatch Gate (GAP-004: BorderGuard Choke Point)
  evaluatePreDispatchAdmission(task, passport, lockManager = null) {
    const lm = lockManager || this.lockManager;
    return BorderGuard.inspect(task, passport, lm);
  }

  // Worker Completion Gate (GAP-003: Worker Global Completion Revocation)
  evaluateWorkerReport(workerReport) {
    return this.completionGovernor.evaluateWorkerReport(workerReport);
  }

  // Mission Status Gate (GAP-003: Only Orchestrator / Governor evaluates global status)
  evaluateMissionStatus(openWorkUnitsCount, isCapacityEnd = false) {
    return this.completionGovernor.evaluateMissionStatus(openWorkUnitsCount, isCapacityEnd);
  }

  // Standard Runtime Process Lifecycle Evaluation (Backward-Compatible with P0)
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

    // Real evidence query for process existence (Phase 5 Telemetry Check)
    let isPidAlive = false;
    try {
      if (lease.pid && typeof lease.pid === 'number') {
        process.kill(lease.pid, 0);
        isPidAlive = true;
      }
    } catch (e) {
      isPidAlive = false;
    }

    // Use StallPolicy for base classification with real evidence / fail-safe UNKNOWN
    const evalResult = this.stallPolicy.evaluateProcessState({
      lease,
      nowMs,
      recentProgressCount: recentEvCount,
      hasActiveSubprocesses: isPidAlive,
      cpuActivityDetected: isPidAlive ? true : 'UNKNOWN',
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
  DecisionEngine,
  BorderGuard,
  TaskPassport,
  CompletionGovernor
};