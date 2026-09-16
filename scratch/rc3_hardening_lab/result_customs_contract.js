/**
 * RESULT CUSTOMS CONTRACT MODEL (ISOLATED LAB)
 * 
 * Formal validation contract for Courier worker task execution envelopes.
 * Supports the 42 standard result envelope fields.
 * Enforces explicit UNKNOWN representation, cryptographic fingerprint verification,
 * evidence consistency, and strict safety invariants.
 * 
 * CRITICAL INVARIANT: Result Customs may accept, hold, or reject a result.
 * It must NEVER mark the entire goal SATISFIED. Goal resolution belongs solely to the Coordinator/Planner.
 */

const crypto = require('crypto');

const RESULT_ENVELOPE_FIELDS = [
  'TASK_ID',
  'TASK_VERSION',
  'GOAL_ID',
  'WORKER_ID',
  'STARTED_AT',
  'FINISHED_AT',
  'STATUS',
  'ORIGINAL_SCOPE_FINGERPRINT',
  'FINAL_SCOPE_FINGERPRINT',
  'SCOPE_CHANGED',
  'EXACT_ACTIONS_PERFORMED',
  'COMMANDS_EXECUTED',
  'FILES_CREATED',
  'FILES_MODIFIED',
  'FILES_DELETED',
  'GIT_HEAD_BEFORE',
  'GIT_HEAD_AFTER',
  'GIT_STATUS_AFTER',
  'TEST_COMMANDS',
  'TESTS_RUN',
  'TESTS_PASS',
  'TESTS_FAIL',
  'TESTS_ERROR',
  'TESTS_SKIP',
  'TEST_EXIT_CODES',
  'ARTIFACTS',
  'LOG_PATHS',
  'ASSUMPTIONS_MADE',
  'DECISIONS_MADE',
  'INVARIANTS_CHECKED',
  'KNOWN_DEFECTS',
  'UNRESOLVED_QUESTIONS',
  'BLOCKERS',
  'HUMAN_GATES',
  'SAFETY_RELEVANT_ACTIONS',
  'EXTERNAL_ACTIONS_PERFORMED',
  'SPEND_PERFORMED',
  'DEPLOYMENTS_PERFORMED',
  'MESSAGES_SENT',
  'RESULT_REFERENCE',
  'RESULT_FINGERPRINT',
  'RECOMMENDED_NEXT_ACTION'
];

class ResultCustoms {
  constructor() {
    this.seenFingerprints = new Set();
    this.acceptedResults = new Map();
    this.rejectionLog = [];
  }

  static computeResultFingerprint(envelope) {
    const payload = {
      task_id: envelope.TASK_ID,
      version: envelope.TASK_VERSION,
      goal_id: envelope.GOAL_ID,
      worker_id: envelope.WORKER_ID,
      status: envelope.STATUS,
      actions: envelope.EXACT_ACTIONS_PERFORMED,
      commands: envelope.COMMANDS_EXECUTED,
      files_created: envelope.FILES_CREATED,
      files_modified: envelope.FILES_MODIFIED,
      git_after: envelope.GIT_HEAD_AFTER,
      tests_pass: envelope.TESTS_PASS,
      tests_fail: envelope.TESTS_FAIL,
      exit_codes: envelope.TEST_EXIT_CODES,
      artifacts: envelope.ARTIFACTS
    };
    return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  }

  static createDefaultEnvelope(overrides = {}) {
    const env = {};
    for (const f of RESULT_ENVELOPE_FIELDS) {
      env[f] = 'UNKNOWN';
    }
    // Set sensible types for collections
    env.EXACT_ACTIONS_PERFORMED = [];
    env.COMMANDS_EXECUTED = [];
    env.FILES_CREATED = [];
    env.FILES_MODIFIED = [];
    env.FILES_DELETED = [];
    env.TEST_COMMANDS = [];
    env.TEST_EXIT_CODES = [];
    env.ARTIFACTS = [];
    env.LOG_PATHS = [];
    env.ASSUMPTIONS_MADE = [];
    env.DECISIONS_MADE = [];
    env.INVARIANTS_CHECKED = [];
    env.KNOWN_DEFECTS = [];
    env.UNRESOLVED_QUESTIONS = [];
    env.BLOCKERS = [];
    env.HUMAN_GATES = [];
    env.SAFETY_RELEVANT_ACTIONS = [];
    env.EXTERNAL_ACTIONS_PERFORMED = [];
    env.DEPLOYMENTS_PERFORMED = [];
    env.MESSAGES_SENT = [];
    env.TESTS_RUN = 0;
    env.TESTS_PASS = 0;
    env.TESTS_FAIL = 0;
    env.TESTS_ERROR = 0;
    env.TESTS_SKIP = 0;
    env.SPEND_PERFORMED = 0;
    env.SCOPE_CHANGED = false;

    Object.assign(env, overrides);
    if (!env.RESULT_FINGERPRINT || env.RESULT_FINGERPRINT === 'UNKNOWN') {
      env.RESULT_FINGERPRINT = ResultCustoms.computeResultFingerprint(env);
    }
    return env;
  }

  validateResult(envelope, expectedContext = {}) {
    const violations = [];

    if (!envelope) {
      return this._reject('UNKNOWN_TASK', ['NIL_ENVELOPE'], 'Envelope is null or undefined');
    }

    const taskId = envelope.TASK_ID;

    // 1. Identity Verification
    if (expectedContext.task_id && envelope.TASK_ID !== expectedContext.task_id) {
      violations.push(`WRONG_TASK_ID: expected ${expectedContext.task_id}, got ${envelope.TASK_ID}`);
    }
    if (expectedContext.version && envelope.TASK_VERSION !== expectedContext.version) {
      violations.push(`WRONG_VERSION: expected ${expectedContext.version}, got ${envelope.TASK_VERSION}`);
    }
    if (expectedContext.goal_id && envelope.GOAL_ID !== expectedContext.goal_id) {
      violations.push(`WRONG_GOAL_ID: expected ${expectedContext.goal_id}, got ${envelope.GOAL_ID}`);
    }
    if (expectedContext.worker_id && envelope.WORKER_ID !== expectedContext.worker_id) {
      violations.push(`WRONG_WORKER_ID: expected ${expectedContext.worker_id}, got ${envelope.WORKER_ID}`);
    }

    // 2. Replay & Fingerprint Verification
    if (!envelope.RESULT_FINGERPRINT || envelope.RESULT_FINGERPRINT === 'UNKNOWN') {
      violations.push('MISSING_RESULT_FINGERPRINT: Result fingerprint is required');
    } else {
      const computedFp = ResultCustoms.computeResultFingerprint(envelope);
      if (envelope.RESULT_FINGERPRINT !== computedFp) {
        violations.push(`FINGERPRINT_MISMATCH: claimed ${envelope.RESULT_FINGERPRINT}, computed ${computedFp}`);
      }
      if (this.seenFingerprints.has(envelope.RESULT_FINGERPRINT)) {
        violations.push(`REPLAYED_RESULT: Fingerprint ${envelope.RESULT_FINGERPRINT} has already been submitted`);
      }
    }

    // 3. Stale Result Check
    if (expectedContext.dispatched_at && envelope.STARTED_AT) {
      if (new Date(envelope.STARTED_AT).getTime() < new Date(expectedContext.dispatched_at).getTime()) {
        violations.push('STALE_RESULT: Task started before current dispatch timestamp');
      }
    }

    // 4. Scope Verification
    if (expectedContext.scope_fingerprint) {
      if (envelope.ORIGINAL_SCOPE_FINGERPRINT !== expectedContext.scope_fingerprint) {
        violations.push(`SCOPE_FINGERPRINT_MISMATCH: expected ${expectedContext.scope_fingerprint}, got ${envelope.ORIGINAL_SCOPE_FINGERPRINT}`);
      }
    }
    if (envelope.SCOPE_CHANGED === true && (!envelope.FINAL_SCOPE_FINGERPRINT || envelope.FINAL_SCOPE_FINGERPRINT === 'UNKNOWN')) {
      violations.push('SCOPE_CHANGE_UNVERIFIED: Scope change claimed but final scope fingerprint missing');
    }

    // 5. Test Evidence Integrity
    if (envelope.TESTS_RUN > 0) {
      if (!Array.isArray(envelope.TEST_COMMANDS) || envelope.TEST_COMMANDS.length === 0) {
        violations.push('CLAIMED_TESTS_WITHOUT_COMMANDS: Tests were reported run but test commands list is empty');
      }
      if (!Array.isArray(envelope.TEST_EXIT_CODES) || envelope.TEST_EXIT_CODES.length === 0) {
        violations.push('CLAIMED_TESTS_WITHOUT_EXIT_CODES: Tests were reported run but test exit codes are missing');
      }
      if (!Array.isArray(envelope.LOG_PATHS) || envelope.LOG_PATHS.length === 0) {
        violations.push('CLAIMED_TESTS_WITHOUT_LOGS: Tests were reported run but log paths are missing');
      }
    }

    // 6. File Evidence Integrity
    if (envelope.FILES_CREATED && envelope.FILES_CREATED.length > 0) {
      for (const f of envelope.FILES_CREATED) {
        if (!f.path || !f.sha256) {
          violations.push(`FILE_CREATED_WITHOUT_EVIDENCE: File ${JSON.stringify(f)} missing path or sha256`);
        }
      }
    }

    // 7. Safety Invariants: No unexpected external actions, spend, deploy, messages
    if (Array.isArray(envelope.EXTERNAL_ACTIONS_PERFORMED) && envelope.EXTERNAL_ACTIONS_PERFORMED.length > 0) {
      violations.push('UNEXPECTED_EXTERNAL_ACTION: External actions detected in completed result');
    }
    if (envelope.SPEND_PERFORMED !== 0 && envelope.SPEND_PERFORMED !== '0') {
      violations.push(`UNEXPECTED_SPEND: Spend reported as ${envelope.SPEND_PERFORMED}, strictly forbidden`);
    }
    if (Array.isArray(envelope.DEPLOYMENTS_PERFORMED) && envelope.DEPLOYMENTS_PERFORMED.length > 0) {
      violations.push('UNEXPECTED_DEPLOYMENT: Production deployments detected in completed result');
    }
    if (Array.isArray(envelope.MESSAGES_SENT) && envelope.MESSAGES_SENT.length > 0) {
      violations.push('UNEXPECTED_MESSAGES_SENT: Outbound messages detected in completed result');
    }

    // 8. Prose PASS without verification
    if (envelope.STATUS === 'PASS') {
      if (envelope.TESTS_RUN > 0 && envelope.TESTS_FAIL > 0) {
        violations.push('CONTRADICTION_PROSE_PASS_WITH_FAILURES: Claimed PASS but tests failed');
      }
      if (envelope.TEST_EXIT_CODES && envelope.TEST_EXIT_CODES.some(code => code !== 0)) {
        violations.push('CONTRADICTION_PROSE_PASS_NONZERO_EXIT: Claimed PASS but test exit code non-zero');
      }
      if (expectedContext.requires_verification_artifact && (!envelope.ARTIFACTS || envelope.ARTIFACTS.length === 0)) {
        violations.push('MISSING_VERIFICATION_ARTIFACT: Worker prose claimed PASS without required verification artifact');
      }
    }

    // Evaluate Acceptance
    if (violations.length > 0) {
      return this._reject(taskId, violations, 'Result envelope rejected due to verification failures');
    }

    // Accept Result
    this.seenFingerprints.add(envelope.RESULT_FINGERPRINT);
    this.acceptedResults.set(taskId, envelope);

    return {
      accepted: true,
      result_status: 'ACCEPTED',
      task_id: taskId,
      result_fingerprint: envelope.RESULT_FINGERPRINT,
      goal_state: 'UNCHANGED', // Invariant: Result Customs NEVER satisfies the goal itself
      summary: 'Result envelope passed all 8 customs checks successfully'
    };
  }

  _reject(taskId, violations, reason) {
    const record = {
      accepted: false,
      result_status: 'REJECTED',
      task_id: taskId,
      violations,
      reason,
      goal_state: 'UNCHANGED',
      timestamp: new Date().toISOString()
    };
    this.rejectionLog.push(record);
    return record;
  }
}

module.exports = {
  RESULT_ENVELOPE_FIELDS,
  ResultCustoms,
  ResultCustomsContract: ResultCustoms
};
