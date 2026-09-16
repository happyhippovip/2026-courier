/**
 * V5 INDEPENDENT SAFETY ORACLES
 * 
 * Formal independent specifications of critical decision gates:
 * 1. DISPATCH_ALLOWED?
 * 2. FALLBACK_ALLOWED?
 * 3. PROCESS_MATCH?
 * 4. PROCESS_KILL_ALLOWED?
 * 5. WRITER_CONFLICT?
 * 6. HUMAN_GATE_REQUIRED?
 * 7. APPROVAL_VALID?
 * 8. RESULT_ACCEPTED?
 * 9. GOAL_SATISFIED?
 * 10. REVENUE_VERIFIED?
 */

const crypto = require('crypto');
const path = require('path');

function sha256(data) {
  const str = typeof data === 'string' ? data : JSON.stringify(data);
  return crypto.createHash('sha256').update(str).digest('hex');
}

class IndependentSafetyOracles {
  // 1. DISPATCH_ALLOWED?
  static isDispatchAllowed(task, systemState) {
    if (task.state === 'EXECUTION_UNCERTAIN') return { allowed: false, reason: 'TASK_EXECUTION_UNCERTAIN' };
    if (task.sideEffectPotential === 'POSSIBLE' && task.startedAt && !task.settled) {
      return { allowed: false, reason: 'SIDE_EFFECT_POSSIBLE_UNSETTLED' };
    }
    if (systemState.hasActiveWriterInScope(task.scope)) return { allowed: false, reason: 'SCOPE_OCCUPIED' };
    if (task.requiresHumanGate && !task.validApprovalToken) return { allowed: false, reason: 'HUMAN_GATE_MISSING' };
    return { allowed: true };
  }

  // 2. FALLBACK_ALLOWED?
  static isFallbackAllowed(task, priorWorkerState) {
    // Fundamental Rule: If prior execution had any chance of side-effect and is not proven clean, NO FALLBACK
    if (task.state === 'EXECUTION_UNCERTAIN' || task.sideEffectPotential === 'POSSIBLE') {
      if (!priorWorkerState.provenClean && !priorWorkerState.externalProofOfNoEffect) {
        return { allowed: false, reason: 'UNCERTAINTY_LOCK_PREVENTS_FALLBACK' };
      }
    }
    return { allowed: true };
  }

  // 3. PROCESS_MATCH?
  static evaluateProcessMatch(lease, osProcess) {
    if (!osProcess || !osProcess.exists) return 'NOT_MATCH';
    if (osProcess.inaccessible || osProcess.startTime === null || osProcess.startTime === undefined) {
      return 'UNKNOWN';
    }
    // Required tuple: PID + StartTime + TaskToken (if command available)
    if (lease.startTime && osProcess.startTime !== lease.startTime) return 'NOT_MATCH';
    if (lease.taskToken && osProcess.taskToken && osProcess.taskToken !== lease.taskToken) return 'NOT_MATCH';
    if (lease.startTime && osProcess.startTime === lease.startTime) return 'MATCH_CONFIRMED';
    return 'UNKNOWN';
  }

  // 4. PROCESS_KILL_ALLOWED?
  static isProcessKillAllowed(procMatch, lease, evidence) {
    if (procMatch === 'NOT_MATCH') return { allowed: false, reason: 'CANNOT_KILL_UNRELATED_PROCESS' };
    if (procMatch === 'UNKNOWN') return { allowed: false, reason: 'CANNOT_KILL_UNKNOWN_PROCESS_FAIL_CLOSED' };
    if (procMatch === 'MATCH_CONFIRMED') {
      if (evidence && evidence.lastActivityMsAgo < 5000) {
        return { allowed: false, reason: 'PROCESS_ACTIVELY_PRODUCING_EVIDENCE' };
      }
      return { allowed: true, reason: 'PROVEN_MATCH_EXPIRED_OR_STALLED' };
    }
    return { allowed: false, reason: 'DEFAULT_FAIL_CLOSED' };
  }

  // 5. WRITER_CONFLICT?
  static isWriterConflict(scopeA, scopeB, caseInsensitive = true) {
    // Both can be arrays or strings
    const listA = Array.isArray(scopeA) ? scopeA : [scopeA];
    const listB = Array.isArray(scopeB) ? scopeB : [scopeB];

    for (const a of listA) {
      for (const b of listB) {
        // Semantic non-filesystem resource check (e.g. 'db:users', 'net:port:8080')
        if (a.includes(':') || b.includes(':')) {
          if (a === b) return true;
          continue;
        }

        // Filesystem path hierarchy check
        let normA = path.normalize(a).replace(/\\/g, '/').replace(/\/$/, '') + '/';
        let normB = path.normalize(b).replace(/\\/g, '/').replace(/\/$/, '') + '/';
        if (caseInsensitive) {
          normA = normA.toLowerCase();
          normB = normB.toLowerCase();
        }
        if (normA === normB || normA.startsWith(normB) || normB.startsWith(normA)) {
          return true;
        }
      }
    }
    return false;
  }

  // 6. HUMAN_GATE_REQUIRED?
  static isHumanGateRequired(actionSpec) {
    const text = (actionSpec.text || '').toLowerCase();
    const tool = actionSpec.tool || {};

    // 1. Tool argument capability inspection (dominant truth)
    if (tool.isSubscription || tool.autoRenew || tool.futureCharge || tool.executeTrade || tool.deployProduction || tool.sendOutreach) {
      return { required: true, reason: 'CAPABILITY_REQUIRES_HUMAN_GATE' };
    }
    if (tool.priceEur && tool.priceEur > 0) {
      return { required: true, reason: 'DIRECT_SPEND_REQUIRES_HUMAN_GATE' };
    }

    // 2. Linguistic analysis: check for explicit informational negation
    const isAnalysisOnly = text.includes('analysis only') || text.includes('do not') || text.includes('without deployment') ||
                           text.includes('simulate ') || text.includes('draft only') || text.includes('paper trade') || text.includes('prepare ');
    
    // Check for deferred liability triggers (these override negation!)
    const hasDeferredLiability = text.includes('auto-renew') || text.includes('future charge') || text.includes('card on file') || text.includes('billing agreement') || text.includes('paid usage') || text.includes('deferred invoice') || text.includes('deferred billing') || text.includes('credit card authorization') || text.includes('card authorization') || text.includes('upgrade to premium') || text.includes('paid tier');
    if (hasDeferredLiability) {
      return { required: true, reason: 'DEFERRED_FINANCIAL_LIABILITY' };
    }

    if (isAnalysisOnly && !text.includes('send outreach') && !text.includes('execute')) {
      return { required: false, reason: 'INFORMATIONAL_ANALYSIS_ONLY' };
    }

    // Action verbs
    const actionTriggers = ['deploy to', 'send outreach', 'execute live trade', 'spend €', 'spend $', 'upgrade execution'];
    for (const act of actionTriggers) {
      if (text.includes(act)) return { required: true, reason: 'DIRECT_EXECUTION_TRIGGER' };
    }

    if (text.includes('deploy') || text.includes('trade') || text.includes('publish') || text.includes('outreach')) {
      return { required: true, reason: 'AMBIGUOUS_ACTION_FAIL_CLOSED' };
    }

    return { required: false, reason: 'SAFE_LOCAL_OPERATION' };
  }

  // 7. APPROVAL_VALID?
  static isApprovalValid(token, requestContext, consumedNoncesSet) {
    if (!token) return { valid: false, reason: 'NO_TOKEN' };
    if (consumedNoncesSet.has(token.nonce)) return { valid: false, reason: 'NONCE_REPLAY_ATTACK' };
    if (token.expiresAt && Date.now() > token.expiresAt) return { valid: false, reason: 'TOKEN_EXPIRED' };
    if (token.taskId && token.taskId !== requestContext.taskId) return { valid: false, reason: 'TASK_ID_MISMATCH' };
    if (token.taskVersion && token.taskVersion !== requestContext.taskVersion) return { valid: false, reason: 'TASK_VERSION_MISMATCH' };
    if (token.operation && token.operation !== requestContext.operation) return { valid: false, reason: 'OPERATION_MISMATCH' };
    if (token.scopeFingerprint && token.scopeFingerprint !== sha256(requestContext.scope)) return { valid: false, reason: 'SCOPE_FINGERPRINT_MISMATCH' };
    return { valid: true };
  }

  // 8. RESULT_ACCEPTED?
  static isResultAccepted(result, task, activeLease) {
    if (!result) return { accepted: false, reason: 'NO_RESULT' };
    if (result.exitCode !== 0) return { accepted: false, reason: 'NONZERO_EXIT_CODE' };
    if (result.taskId !== task.id) return { accepted: false, reason: 'RESULT_TASK_ID_MISMATCH' };
    if (result.taskVersion !== task.version) return { accepted: false, reason: 'RESULT_TASK_VERSION_STALE' };
    if (result.goalId !== task.goalId) return { accepted: false, reason: 'RESULT_GOAL_ID_MISMATCH' };
    if (result.payloadHash !== sha256(result.payload)) return { accepted: false, reason: 'PAYLOAD_CHECKSUM_FAILED' };
    if (!activeLease || activeLease.status !== 'ACTIVE' || activeLease.workerId !== result.workerId) {
      return { accepted: false, reason: 'RESULT_SUBMITTED_AGAINST_EXPIRED_OR_STALE_LEASE' };
    }
    return { accepted: true };
  }

  // 9. GOAL_SATISFIED?
  static isGoalSatisfied(goal, childTasks, verificationProof) {
    for (const c of childTasks) {
      if (c.status !== 'COMPLETE' && c.status !== 'SATISFIED') {
        return { satisfied: false, reason: `CHILD_TASK_UNRESOLVED_${c.id}_${c.status}` };
      }
    }
    if (!verificationProof || !verificationProof.verified) {
      return { satisfied: false, reason: 'MISSING_VERIFICATION_PROOF' };
    }
    if (verificationProof.workspaceFingerprint !== goal.currentWorkspaceFingerprint) {
      return { satisfied: false, reason: 'WORKSPACE_FINGERPRINT_DRIFT' };
    }
    return { satisfied: true };
  }

  // 10. REVENUE_VERIFIED?
  static isRevenueVerified(claim) {
    if (!claim || claim.claimedAmountEur <= 0) return { verified: true, recognizedEur: 0.00 };
    // Real revenue requires cryptographic settlement signature from Stripe/Banking provider
    if (!claim.settlementProof || claim.settlementProof.type !== 'CRYPTOGRAPHIC_BANKING_OR_STRIPE_WEBHOOK') {
      return { verified: false, recognizedEur: 0.00, reason: 'SIMULATED_OR_UNSETTLED_RECEIPT' };
    }
    if (!claim.settlementProof.bankDepositConfirmed) {
      return { verified: false, recognizedEur: 0.00, reason: 'PENDING_DEPOSIT_NOT_SETTLED' };
    }
    return { verified: true, recognizedEur: claim.claimedAmountEur };
  }
}

module.exports = { IndependentSafetyOracles, sha256 };
