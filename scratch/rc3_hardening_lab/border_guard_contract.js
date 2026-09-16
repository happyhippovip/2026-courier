/**
 * BORDER GUARD / MESSAGE CUSTOMS CONTRACT (ISOLATED LAB)
 * 
 * Formal contract protecting outbound worker dispatch and inbound responses.
 * Enforces:
 * - Outbound decisions: GREEN_CARD, REVISE, HOLD, BLOCK, ESCALATE
 * - Strict blocking of: spend, deploy, publication, external messages, trading,
 *   wallets, credentials, test weakening requests, uncertain execution.
 * - Validation of: worker conflict, duplicate task, stale task, wrong version,
 *   insufficient acceptance criteria, missing evidence requirements.
 * - Worker response protocol: ACCEPT, QUESTION, CONFLICT, NEEDS_SCOPE_CHANGE,
 *   BETTER_ALTERNATIVE, INSUFFICIENT_EVIDENCE, UNSAFE, DUPLICATE_WORK, ALREADY_DONE, UNAVAILABLE.
 * - Bounded Appeal: Exactly ONE appeal allowed. Re-appealing is strictly blocked (no loop).
 */

const crypto = require('crypto');

const OUTBOUND_DECISION = Object.freeze({
  GREEN_CARD: 'GREEN_CARD',
  REVISE: 'REVISE',
  HOLD: 'HOLD',
  BLOCK: 'BLOCK',
  ESCALATE: 'ESCALATE'
});

const WORKER_RESPONSE = Object.freeze({
  ACCEPT: 'ACCEPT',
  QUESTION: 'QUESTION',
  CONFLICT: 'CONFLICT',
  NEEDS_SCOPE_CHANGE: 'NEEDS_SCOPE_CHANGE',
  BETTER_ALTERNATIVE: 'BETTER_ALTERNATIVE',
  INSUFFICIENT_EVIDENCE: 'INSUFFICIENT_EVIDENCE',
  UNSAFE: 'UNSAFE',
  DUPLICATE_WORK: 'DUPLICATE_WORK',
  ALREADY_DONE: 'ALREADY_DONE',
  UNAVAILABLE: 'UNAVAILABLE'
});

const PROHIBITED_KEYWORDS = [
  /\bspend\b/i,
  /\bbilling\b/i,
  /\bcredit_card\b/i,
  /\bdeploy_to_prod\b/i,
  /\bpublish_public\b/i,
  /\bsend_email\b/i,
  /\bsend_sms\b/i,
  /\bcontact_customer\b/i,
  /\btrade\b/i,
  /\bwallet\b/i,
  /\bapi_key\b/i,
  /\bpassword\b/i,
  /\bskip_test\b/i,
  /\bweaken_test\b/i,
  /\bignore_failure\b/i
];

class BorderGuard {
  constructor() {
    this.activeDispatches = new Map(); // taskId -> envelope
    this.appeals = new Map(); // taskId -> count
    this.auditLog = [];
  }

  evaluateOutbound(envelope, context = {}) {
    if (!envelope || !envelope.task_id) {
      throw new Error('[BORDER_GUARD_ERROR] Valid task envelope with task_id required');
    }

    const taskId = envelope.task_id;
    const checksFailed = [];

    // 1. Critical Hard Safety Boundaries (Fail-Closed BLOCK)
    if (envelope.spend_requested || envelope.spend_amount_eur > 0) {
      checksFailed.push({ code: 'BLOCK_SPEND_FORBIDDEN', reason: 'Financial spend strictly prohibited' });
    }
    if (envelope.deploy_intent || envelope.production_target) {
      checksFailed.push({ code: 'BLOCK_DEPLOY_FORBIDDEN', reason: 'Production deployment strictly prohibited' });
    }
    if (envelope.publication_intent) {
      checksFailed.push({ code: 'BLOCK_PUBLICATION_FORBIDDEN', reason: 'Public publication strictly prohibited' });
    }
    if (envelope.external_message_intent) {
      checksFailed.push({ code: 'BLOCK_EXTERNAL_MESSAGE_FORBIDDEN', reason: 'External messaging strictly prohibited' });
    }
    if (envelope.trade_intent || envelope.wallet_connection) {
      checksFailed.push({ code: 'BLOCK_TRADE_WALLET_FORBIDDEN', reason: 'Trading and wallet operations strictly prohibited' });
    }
    if (envelope.requires_credential_entry) {
      return this._decide(taskId, OUTBOUND_DECISION.ESCALATE, 'Human coordinator credential gate required', ['HUMAN_GATE_CREDENTIALS']);
    }
    if (envelope.weaken_test_assertions === true) {
      checksFailed.push({ code: 'BLOCK_TEST_WEAKENING_FORBIDDEN', reason: 'Weakening test assertions strictly forbidden' });
    }
    if (envelope.execution_state_uncertain === true) {
      checksFailed.push({ code: 'BLOCK_EXECUTION_UNCERTAIN', reason: 'Prior execution uncertain: redispatch strictly blocked' });
    }

    // Inspect command / description for prohibited operations
    const textToCheck = `${envelope.command || ''} ${envelope.description || ''}`;
    for (const pat of PROHIBITED_KEYWORDS) {
      if (pat.test(textToCheck)) {
        checksFailed.push({ code: 'BLOCK_PROHIBITED_KEYWORD', reason: `Prohibited operation detected: ${pat}` });
      }
    }

    if (checksFailed.length > 0) {
      return this._decide(taskId, OUTBOUND_DECISION.BLOCK, 'Task violates hard safety boundary', checksFailed.map(c => c.code));
    }

    // 2. Concurrency & Scope Conflicts (HOLD)
    if (context.activeWorkerIds && context.activeWorkerIds.includes(envelope.worker_id)) {
      return this._decide(taskId, OUTBOUND_DECISION.HOLD, `Worker ${envelope.worker_id} is currently busy with in-flight task`, ['WORKER_CONFLICT']);
    }
    if (context.activeTaskIds && context.activeTaskIds.includes(envelope.task_id)) {
      return this._decide(taskId, OUTBOUND_DECISION.HOLD, `Task ${envelope.task_id} is already in-flight (duplicate dispatch blocked)`, ['DUPLICATE_TASK']);
    }
    if (context.conflictingScopes && context.conflictingScopes.length > 0) {
      return this._decide(taskId, OUTBOUND_DECISION.HOLD, `Scope conflict with active task on ${context.conflictingScopes.join(', ')}`, ['SCOPE_CONFLICT']);
    }

    // 3. Completeness & Quality Guards (REVISE)
    if (!envelope.acceptance_criteria || envelope.acceptance_criteria.length === 0) {
      return this._decide(taskId, OUTBOUND_DECISION.REVISE, 'Acceptance criteria missing or empty', ['INSUFFICIENT_ACCEPTANCE_CRITERIA']);
    }
    if (!envelope.required_evidence || envelope.required_evidence.length === 0) {
      return this._decide(taskId, OUTBOUND_DECISION.REVISE, 'Required evidence types not specified', ['MISSING_EVIDENCE_REQUIREMENT']);
    }
    if (envelope.is_stale || (envelope.expected_head && context.currentGitHead && envelope.expected_head !== context.currentGitHead)) {
      return this._decide(taskId, OUTBOUND_DECISION.REVISE, 'Task is based on stale git HEAD snapshot', ['STALE_TASK']);
    }
    if (envelope.version && context.latestKnownVersion && envelope.version <= context.latestKnownVersion) {
      return this._decide(taskId, OUTBOUND_DECISION.REVISE, `Version ${envelope.version} is not newer than latest version ${context.latestKnownVersion}`, ['WRONG_VERSION']);
    }

    // 4. Optimization advisory (REVISE with better route)
    if (context.cheaperSaferAlternative) {
      return this._decide(taskId, OUTBOUND_DECISION.REVISE, `Better/cheaper safe route available: ${context.cheaperSaferAlternative}`, ['BETTER_ALTERNATIVE_AVAILABLE']);
    }

    // 5. Passed all checks -> GREEN_CARD
    return this._decide(taskId, OUTBOUND_DECISION.GREEN_CARD, 'Task qualified for dispatch with zero objections', ['CLEAR']);
  }

  processAppeal(taskId, revisedEnvelope, justification) {
    const currentAppeals = this.appeals.get(taskId) || 0;

    // Strict Anti-Loop: Exactly one appeal allowed
    if (currentAppeals >= 1) {
      this._log(taskId, 'APPEAL_REJECTED_LOOP_PREVENTED', { currentAppeals });
      return {
        appeal_accepted: false,
        action: 'TERMINAL_BLOCK',
        decision: OUTBOUND_DECISION.BLOCK,
        reason: 'Appeal limit exceeded (maximum 1 appeal per task). Infinite appeal loop prevented.'
      };
    }

    this.appeals.set(taskId, currentAppeals + 1);
    this._log(taskId, 'APPEAL_SUBMITTED', { appealCount: currentAppeals + 1, justification });

    // Re-evaluate revised envelope
    const evalResult = this.evaluateOutbound(revisedEnvelope);
    return {
      appeal_accepted: evalResult.decision === OUTBOUND_DECISION.GREEN_CARD,
      decision: evalResult.decision,
      appeal_count: currentAppeals + 1,
      details: evalResult
    };
  }

  handleWorkerResponse(taskId, responseType, details = {}) {
    if (!Object.values(WORKER_RESPONSE).includes(responseType)) {
      throw new Error(`[WORKER_RESPONSE_ERROR] Unknown worker response type: ${responseType}`);
    }

    this._log(taskId, 'WORKER_RESPONSE_RECEIVED', { responseType, details });

    switch (responseType) {
      case WORKER_RESPONSE.ACCEPT:
        return { action: 'PROCEED_IN_FLIGHT', status: 'IN_FLIGHT' };
      case WORKER_RESPONSE.QUESTION:
      case WORKER_RESPONSE.NEEDS_SCOPE_CHANGE:
      case WORKER_RESPONSE.BETTER_ALTERNATIVE:
      case WORKER_RESPONSE.INSUFFICIENT_EVIDENCE:
        return { action: 'RETURN_TO_NEGOTIATION', status: 'NEGOTIATING', reason: details.reason || responseType };
      case WORKER_RESPONSE.CONFLICT:
      case WORKER_RESPONSE.DUPLICATE_WORK:
      case WORKER_RESPONSE.ALREADY_DONE:
      case WORKER_RESPONSE.UNAVAILABLE:
        return { action: 'PLACE_ON_HOLD_OR_CLOSE', status: 'HOLD', reason: details.reason || responseType };
      case WORKER_RESPONSE.UNSAFE:
        return { action: 'HALT_AND_ESCALATE', status: 'BLOCKED', reason: details.reason || 'Worker flagged task as UNSAFE' };
      default:
        return { action: 'UNKNOWN_FALLBACK', status: 'HOLD' };
    }
  }

  _decide(taskId, decision, summary, reasonCodes = []) {
    const fingerprint = crypto.createHash('sha256').update(`${taskId}:${decision}:${summary}:${reasonCodes.join('|')}`).digest('hex');
    const record = {
      timestamp: new Date().toISOString(),
      task_id: taskId,
      decision,
      summary,
      reason_codes: reasonCodes,
      fingerprint
    };
    this.auditLog.push(record);
    return record;
  }

  _log(taskId, event, details = {}) {
    this.auditLog.push({
      timestamp: new Date().toISOString(),
      task_id: taskId,
      event,
      details
    });
  }
}

module.exports = {
  OUTBOUND_DECISION,
  WORKER_RESPONSE,
  BorderGuard
};
