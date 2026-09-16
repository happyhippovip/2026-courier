/**
 * V3 SHADOW COURIER HARNESS & PACKAGE IMPLEMENTATIONS
 * 
 * Implements isolated, non-dispatching shadow contracts for:
 * - PKG-001: Task Stamp
 * - PKG-002: Worker Lease
 * - PKG-003: Process Lease
 * - PKG-004: No-Stacking Scope Concurrency
 * - PKG-005: Follow-Up Inbox
 * - PKG-006: Border Guard & TOCTOU
 * - PKG-007: Result Customs & Passport
 * - PKG-008: Crash Reconciliation
 * - PKG-009: Execution Uncertainty
 * - PKG-010: Resource Governor
 * - PKG-011: Task Hygiene
 * - PKG-012: Terminal Satisfaction
 * - PKG-013: Logical Work Identity
 * - PKG-014: Fallback Routing
 * - PKG-015: Event Ledger
 * - PKG-016: Diagnostic Bundle
 * - PKG-017: Chief Escalation Envelope
 * - PKG-018: Money Factory Compatibility & Requests (Spend, Publish, Outreach)
 * - PKG-019: Human-Gate Scoping & Replay Defense
 * - PKG-020: Cross-Machine Origin Tracking
 */

const crypto = require('crypto');

// Utility for deterministic fingerprinting
function sha256(data) {
  const str = typeof data === 'string' ? data : JSON.stringify(data);
  return crypto.createHash('sha256').update(str).digest('hex');
}

// PKG-001: Task Stamp
class ShadowTaskStamp {
  static createStamp(taskParams) {
    const required = ['task_id', 'task_version', 'goal_id', 'scope', 'risk', 'acceptance_criteria', 'writer_class'];
    for (const f of required) {
      if (!taskParams[f]) throw new Error(`Missing required stamp field: ${f}`);
    }

    const stamp = {
      ...taskParams,
      instruction_fingerprint: sha256(taskParams.instruction || ''),
      scope_fingerprint: sha256(taskParams.scope),
      stamped_at: new Date().toISOString(),
      frozen: true
    };
    return Object.freeze(stamp);
  }

  static attemptMutation(stamp, field, value) {
    if (stamp.frozen) {
      return { allowed: false, code: 'POST_STAMP_MUTATION_BLOCKED', reason: 'Stamped tasks are strictly immutable' };
    }
    stamp[field] = value;
    return { allowed: true };
  }
}

// PKG-002: Worker Lease
class ShadowWorkerLease {
  constructor() {
    this.activeLeases = new Map(); // scopeKey -> lease
  }

  acquireLease(workerId, scope, isWriter, goalId, taskVersion) {
    const scopeKey = Array.isArray(scope) ? scope.sort().join('|') : String(scope);
    const existing = this.activeLeases.get(scopeKey);

    if (existing) {
      if (existing.isWriter && isWriter) {
        return { acquired: false, code: 'LEASE_CONFLICT_WRITER_EXISTS', current_holder: existing.workerId };
      }
      if (existing.isWriter && !isWriter) {
        return { acquired: false, code: 'LEASE_CONFLICT_WRITER_BLOCKS_READ', current_holder: existing.workerId };
      }
      if (!existing.isWriter && isWriter) {
        return { acquired: false, code: 'LEASE_CONFLICT_READERS_BLOCK_WRITE' };
      }
    }

    const lease = {
      lease_id: 'LEASE_' + Math.random().toString(36).substr(2, 9),
      workerId,
      scopeKey,
      isWriter,
      goalId,
      taskVersion,
      acquired_at: Date.now(),
      status: 'ACTIVE'
    };
    this.activeLeases.set(scopeKey, lease);
    return { acquired: true, lease };
  }

  releaseLease(scopeKey) {
    return this.activeLeases.delete(scopeKey);
  }
}

// PKG-003: Process Lease
class ShadowProcessLease {
  static createProcessLease(leaseParams) {
    return {
      process_lease_id: 'PROC_LEASE_' + Math.random().toString(36).substr(2, 9),
      task_id: leaseParams.task_id,
      task_version: leaseParams.task_version,
      goal_id: leaseParams.goal_id,
      worker_id: leaseParams.worker_id,
      machine_id: leaseParams.machine_id,
      pid: leaseParams.pid,
      ppid: leaseParams.ppid,
      process_fingerprint: sha256(`${leaseParams.pid}:${leaseParams.started_at}`),
      command_fingerprint: sha256(leaseParams.command_line || ''),
      purpose: leaseParams.purpose || 'EXECUTION',
      started_at: leaseParams.started_at,
      last_heartbeat_at: leaseParams.started_at,
      last_progress_at: leaseParams.started_at,
      status: 'RUNNING'
    };
  }

  static verifyProcessOwnership(lease, currentProcess) {
    if (lease.pid !== currentProcess.pid) return { match: false, reason: 'PID mismatch' };
    if (lease.started_at !== currentProcess.started_at) {
      return { match: false, reason: 'PID recycled (start time mismatch)', code: 'PID_REUSED_UNAUTHORIZED' };
    }
    return { match: true };
  }
}

// PKG-004: No-Stacking Scope Concurrency
class ShadowNoStacking {
  static checkCollision(existingTasks, newTask) {
    for (const t of existingTasks) {
      if (t.status !== 'RUNNING' && t.status !== 'DISPATCHED') continue;

      // Check overlap in declared scopes
      const hasOverlap = t.scope.some(s => newTask.scope.includes(s));
      if (hasOverlap) {
        if (t.writer_class === 'EXCLUSIVE_WRITER' || newTask.writer_class === 'EXCLUSIVE_WRITER') {
          return { collision: true, action: 'HOLD', reason: `Scope conflict with in-flight task ${t.task_id}` };
        }
      }
    }
    return { collision: false, action: 'DISPATCH_ALLOWED' };
  }
}

// PKG-005: Follow-Up Inbox
class ShadowFollowUpInbox {
  constructor() {
    this.inbox = [];
  }

  submitFollowUp(entry) {
    const item = {
      follow_up_id: 'FU_' + (this.inbox.length + 1),
      goal_id: entry.goal_id,
      task_id: entry.task_id,
      source: entry.source,
      thought: entry.thought,
      reason: entry.reason,
      priority: entry.priority || 'NORMAL',
      dependency: entry.dependency || null,
      status: 'PENDING',
      created_at: new Date().toISOString()
    };
    this.inbox.push(item);
    return item;
  }
}

// PKG-006: Border Guard & TOCTOU
class ShadowBorderGuard {
  static evaluateOutbound(envelope, action, stateVersion, approvedStateVersion) {
    if (stateVersion !== approvedStateVersion) {
      return { decision: 'BLOCK', code: 'TOCTOU_STATE_VERSION_MUTATED', reason: 'Task state changed between review and dispatch' };
    }

    if (action.type === 'SPEND') {
      return { decision: 'BLOCK', code: 'SPEND_BLOCKED', reason: 'Spend strictly prohibited in hardening mode' };
    }
    if (action.type === 'NETWORK_EGRESS' && !envelope.allow_network) {
      return { decision: 'BLOCK', code: 'NETWORK_BLOCKED', reason: 'Undeclared network egress blocked' };
    }
    return { decision: 'GREEN_CARD', code: 'ACTION_AUTHORIZED' };
  }

  static handleWorkerAppeal(workerStatus, appealCount) {
    if (appealCount >= 1) {
      return { allowed: false, decision: 'REJECTED_FINAL', reason: 'Maximum 1 appeal allowed' };
    }
    return { allowed: true, decision: 'APPEAL_ACCEPTED_FOR_EVALUATION' };
  }
}

// PKG-007: Result Customs & Passport
class ShadowResultCustoms {
  static inspectResult(resultEnvelope) {
    if (!resultEnvelope || !resultEnvelope.machine_proof) {
      return { accepted: false, code: 'PROSE_REJECTED', reason: 'Worker narrative without machine proof is rejected' };
    }
    if (resultEnvelope.machine_proof.exit_code !== 0) {
      return { accepted: false, code: 'NON_ZERO_EXIT_CODE', reason: 'Process exited with error' };
    }
    return { accepted: true, code: 'RESULT_VERIFIED' };
  }

  static verifyFreshness(resultEnvelope, currentTask) {
    if (resultEnvelope.task_id !== currentTask.task_id) return { fresh: false, reason: 'Task ID mismatch' };
    if (resultEnvelope.task_version !== currentTask.task_version) return { fresh: false, reason: 'Stale task version' };
    if (resultEnvelope.goal_id !== currentTask.goal_id) return { fresh: false, reason: 'Goal ID mismatch' };
    return { fresh: true };
  }
}

// PKG-008: Crash Reconciliation Engine
class ShadowCrashReconciler {
  static reconcileCrash(stateAtCrash) {
    switch (stateAtCrash) {
      case 'STAMPED':
        return { action: 'SAFE_TO_REDISPATCH', resume_state: 'STAMPED' };
      case 'DISPATCHED':
      case 'IN_FLIGHT':
        return { action: 'HOLD_EXECUTION_UNCERTAIN', resume_state: 'EXECUTION_UNCERTAIN', redispatch: false };
      case 'RESULT_RECEIVED':
      case 'PENDING_VERIFY':
        return { action: 'PROCEED_TO_VERIFY', resume_state: 'PENDING_VERIFY', redispatch: false };
      case 'VERIFIED':
        return { action: 'PRESERVE_VERIFIED_OUTCOME', resume_state: 'VERIFIED' };
      default:
        return { action: 'HOLD_UNKNOWN', resume_state: 'BLOCKED' };
    }
  }
}

// PKG-009: Execution Uncertainty
class ShadowExecutionUncertainty {
  static evaluateRedispatchEligibility(effectClassification) {
    if (effectClassification === 'DEFINITE_NO_EFFECT') {
      return { redispatch_eligible: true, action: 'ALLOW_FALLBACK_OR_RETRY' };
    }
    if (effectClassification === 'RESULT_PRESENT' || effectClassification === 'PENDING_VERIFY') {
      return { redispatch_eligible: false, action: 'ROUTE_TO_VERIFICATION' };
    }
    // POSSIBLE_EFFECT_NO_PROOF or UNCERTAIN
    return { redispatch_eligible: false, action: 'BLOCK_REDISPATCH_FAIL_CLOSED' };
  }
}

// PKG-010: Resource Governor
class ShadowResourceGovernor {
  constructor() {
    this.machineStates = new Map();
  }

  setMachineState(machineId, state) {
    this.machineStates.set(machineId, state);
  }

  isMachineEligible(machineId) {
    const state = this.machineStates.get(machineId) || 'NORMAL';
    return state !== 'THERMAL_PRESSURE' && state !== 'OUT_OF_MEMORY';
  }
}

// PKG-011: Task Hygiene
class ShadowTaskHygiene {
  static evaluateProgress(elapsedMs, logGrownBytes, isExpectedWait) {
    if (isExpectedWait) return { decision: 'KEEP', action: 'MAINTAIN_EXECUTION' };
    if (elapsedMs >= 900000 && logGrownBytes === 0) {
      return { decision: 'DIAGNOSE', action: 'CAPTURE_DIAGNOSTIC_BUNDLE' };
    }
    if (elapsedMs >= 300000 && logGrownBytes === 0) {
      return { decision: 'KEEP', action: 'PROBE_PROGRESS' };
    }
    return { decision: 'KEEP', action: 'MAINTAIN_EXECUTION' };
  }
}

// PKG-012: Terminal Satisfaction
class ShadowTerminalSatisfaction {
  static verifySatisfaction(claim) {
    if (!claim.goal_id || !claim.mission_id || !claim.logical_work_id) {
      return { satisfied: false, reason: 'Missing core identity references' };
    }
    if (!claim.deterministic_pass) {
      return { satisfied: false, reason: 'Deterministic test pass required' };
    }
    if (claim.empty_queue_only) {
      return { satisfied: false, reason: 'Empty queue alone is not satisfaction proof' };
    }
    return { satisfied: true, code: 'TERMINAL_SATISFACTION_CERTIFIED' };
  }
}

// PKG-013 & PKG-014: Logical Work Identity & Fallback Routing
class ShadowWorkIdentity {
  static computeLogicalId(payload) {
    // Exclude routing metadata (worker_id, attempt, transport)
    const canonical = {
      criteria: payload.criteria || payload.acceptance_criteria || [],
      goal_id: payload.goal_id,
      instruction: payload.instruction || '',
      scope: (payload.scope || []).slice().sort()
    };
    const sortedKeys = Object.keys(canonical).sort();
    return sha256(JSON.stringify(canonical, sortedKeys));
  }

  static routeChangePreservesIdentity(payloadA, payloadBWithNewRoute) {
    return this.computeLogicalId(payloadA) === this.computeLogicalId(payloadBWithNewRoute);
  }
}

// PKG-015: Event Ledger
class ShadowEventLedger {
  constructor() {
    this.entries = [];
  }

  appendEvent(event) {
    const seq = this.entries.length;
    const prevHash = seq === 0 ? 'GENESIS_HASH' : this.entries[seq - 1].hash;
    const entryObj = { seq, prev_hash: prevHash, event, timestamp: new Date().toISOString() };
    const hash = sha256(entryObj);
    const completeBlock = { ...entryObj, hash };
    this.entries.push(completeBlock);
    return completeBlock;
  }
}

// PKG-016: Diagnostic Bundle
class ShadowDiagnosticBundle {
  static createBundle(params) {
    return {
      bundle_id: 'DIAG_' + Math.random().toString(36).substr(2, 9),
      machine_telemetry: { host: 'WINDOWS', cpu: params.cpu, ram_mb: params.ram },
      task_state: params.task_state,
      process_state: params.process_state,
      repo_state: { branch: params.branch, head: params.head },
      evidence_refs: params.evidence_refs || [],
      created_at: new Date().toISOString()
    };
  }
}

// PKG-017: Chief Escalation Envelope
class ShadowChiefEnvelope {
  static createEscalation(params) {
    return {
      envelope_type: 'SUPERVISOR_REVIEW_REQUEST',
      task_id: params.task_id,
      goal_id: params.goal_id,
      reason: params.reason,
      classification: params.classification,
      evidence_refs: params.evidence_refs,
      diagnostic_bundle_ref: params.diagnostic_bundle_ref,
      screenshot_ref: params.screenshot_ref || null,
      risk: params.risk || 'MEDIUM',
      recommended_action: params.recommended_action,
      confidence: params.confidence || 0.95
    };
  }
}

// PKG-018: Money Factory Compatibility & Request Envelopes
class ShadowMoneyFactoryAdapter {
  static createSpendRequest(params) {
    return {
      request_type: 'SPEND_REQUEST',
      goal_id: params.goal_id,
      amount: params.amount,
      currency: params.currency || 'EUR',
      purpose: params.purpose,
      human_approval_required: true,
      executed: false
    };
  }

  static createPublicationRequest(params) {
    return {
      request_type: 'PUBLICATION_REQUEST',
      goal_id: params.goal_id,
      channel: params.channel,
      human_approval_required: true,
      published: false
    };
  }

  static createOutreachRequest(params) {
    return {
      request_type: 'OUTREACH_REQUEST',
      recipient: params.recipient,
      human_approval_required: true,
      sent: false
    };
  }
}

// PKG-019: Human Gate Classifier & Scoping
class ShadowHumanGateScoping {
  static validateApproval(approvalToken, requestedAction) {
    if (!approvalToken || !approvalToken.signature) {
      return { valid: false, code: 'APPROVAL_MISSING' };
    }
    if (approvalToken.used) {
      return { valid: false, code: 'APPROVAL_REPLAY_BLOCKED', reason: 'One-time approval token already used' };
    }
    if (approvalToken.task_id !== requestedAction.task_id) {
      return { valid: false, code: 'WRONG_TASK_SCOPE', reason: 'Token scoped to different task' };
    }
    if (approvalToken.operation !== requestedAction.operation) {
      return { valid: false, code: 'WRONG_OPERATION_SCOPE', reason: 'Token scoped to different operation' };
    }
    return { valid: true, code: 'APPROVAL_AUTHORIZED' };
  }
}

// PKG-020: Cross-Machine Origin Tracking
class ShadowCrossMachineOrigin {
  static tagOrigin(task, hostMachine) {
    return {
      ...task,
      origin_machine: hostMachine,
      origin_timestamp: new Date().toISOString()
    };
  }
}

module.exports = {
  ShadowTaskStamp,
  ShadowWorkerLease,
  ShadowProcessLease,
  ShadowNoStacking,
  ShadowFollowUpInbox,
  ShadowBorderGuard,
  ShadowResultCustoms,
  ShadowCrashReconciler,
  ShadowExecutionUncertainty,
  ShadowResourceGovernor,
  ShadowTaskHygiene,
  ShadowTerminalSatisfaction,
  ShadowWorkIdentity,
  ShadowEventLedger,
  ShadowDiagnosticBundle,
  ShadowChiefEnvelope,
  ShadowMoneyFactoryAdapter,
  ShadowHumanGateScoping,
  ShadowCrossMachineOrigin
};
