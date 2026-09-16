/**
 * BORDER GUARD & CUSTOMS VERIFICATION ENGINE V2
 * 
 * Formal models for Campaigns 016 – 023:
 * - Campaign 016: Border Guard Outbound Enforcement
 * - Campaign 017: TOCTOU State Mutation Protection
 * - Campaign 018: Worker Rights & Negotiation Protocol
 * - Campaign 019: Bounded Appeal Anti-Loop
 * - Campaign 020: 42-Field Passport Forgery & Tamper Resistance
 * - Campaign 021: Prose-as-Proof Rejection
 * - Campaign 022: Test-Weakening Detection
 * - Campaign 023: False Terminal Satisfaction Invariant
 */

const crypto = require('crypto');

class BorderAndCustomsEngine {
  constructor() {
    this.appealCounts = new Map(); // taskId -> count
    this.seenNonces = new Set();
  }

  /**
   * CAMPAIGN 016: Border Guard Outbound Enforcement
   */
  static evaluateOutboundAction(envelope, action) {
    if (!envelope || !envelope.permissions) {
      return { allowed: false, code: 'PERMISSION_DENIED_NO_POLICY', reason: 'Missing execution permissions envelope.' };
    }

    const { allowed_actions = [], allowed_paths = [], allow_network = false, allow_spend = false } = envelope.permissions;

    if (action.type === 'SPEND' || action.type === 'WALLET_TRANSACTION' || action.type === 'TRADE') {
      if (!allow_spend) {
        return { allowed: false, code: 'SECURITY_VIOLATION_SPEND_BLOCKED', reason: 'Spend/trade actions are strictly prohibited.' };
      }
    }

    if (action.type === 'NETWORK_EGRESS') {
      if (!allow_network) {
        return { allowed: false, code: 'SECURITY_VIOLATION_NETWORK_BLOCKED', reason: 'Outbound network egress is prohibited.' };
      }
    }

    if (action.type === 'FILE_WRITE') {
      const targetPath = action.target_path || '';
      const isPathAllowed = allowed_paths.some(prefix => targetPath.startsWith(prefix));
      if (!isPathAllowed) {
        return { allowed: false, code: 'SECURITY_VIOLATION_PATH_ESCAPED', reason: `File write to ${targetPath} is outside allowed directories.` };
      }
    }

    if (!allowed_actions.includes(action.type)) {
      return { allowed: false, code: 'ACTION_NOT_PERMITTED', reason: `Action ${action.type} is not declared in envelope.` };
    }

    return { allowed: true, code: 'ACTION_PERMITTED', reason: 'Action authorized by task permissions envelope.' };
  }

  /**
   * CAMPAIGN 017: TOCTOU State Mutation Protection
   */
  static verifyAtomicPayloadExecution(inspectedHash, actualPayload) {
    const actualHash = crypto.createHash('sha256').update(JSON.stringify(actualPayload)).digest('hex');
    if (inspectedHash !== actualHash) {
      return {
        valid: false,
        code: 'TOCTOU_HASH_MISMATCH',
        reason: `Payload changed between inspection (${inspectedHash}) and execution (${actualHash}).`,
        action: 'REVOKE_LEASE_AND_ABORT'
      };
    }
    return {
      valid: true,
      code: 'TOCTOU_VERIFIED',
      reason: 'Atomic payload execution verified; hash unchanged.'
    };
  }

  /**
   * CAMPAIGN 018: Worker Rights & Negotiation Protocol
   */
  static handleWorkerFeedback(taskState, feedback) {
    if (!feedback || !feedback.status) {
      return { action: 'REJECT_MALFORMED_FEEDBACK', new_state: taskState.status };
    }

    if (feedback.status === 'CAPACITY_EXCEEDED' || feedback.status === 'RESOURCE_CONSTRAINED') {
      return {
        action: 'NEGOTIATION_ACKNOWLEDGED',
        new_state: 'PAUSED_FOR_CAPACITY',
        preserve_canonical_hash: true,
        reassign_eligible: true,
        reason: 'Worker exercised rights under constraint; task state preserved without fault.'
      };
    }

    if (feedback.status === 'UNSUPPORTED_CAPABILITY') {
      return {
        action: 'ROUTE_TO_SPECIALIZED_WORKER',
        new_state: 'RE_ROUTING',
        preserve_canonical_hash: true,
        reason: 'Worker lacked required runtime; moving to compatible route.'
      };
    }

    return { action: 'PROCESS_NORMAL_FEEDBACK', new_state: taskState.status };
  }

  /**
   * CAMPAIGN 019: Bounded Appeal Anti-Loop
   */
  handleWorkerAppeal(taskId, appealReason) {
    const currentAppeals = this.appealCounts.get(taskId) || 0;
    const MAX_APPEALS = 3;

    if (currentAppeals >= MAX_APPEALS) {
      return {
        allowed: false,
        code: 'APPEAL_LIMIT_EXCEEDED',
        appeals_made: currentAppeals,
        final_state: 'REJECTED_FINAL',
        reason: `Task ${taskId} exceeded maximum allowed appeals (${MAX_APPEALS}). Infinite loop prevented.`
      };
    }

    this.appealCounts.set(taskId, currentAppeals + 1);
    return {
      allowed: true,
      code: 'APPEAL_ACCEPTED_FOR_REVIEW',
      appeals_made: currentAppeals + 1,
      appeals_remaining: MAX_APPEALS - (currentAppeals + 1),
      reason: 'Appeal registered within allowed bound.'
    };
  }

  /**
   * CAMPAIGN 020: 42-Field Passport Forgery & Tamper Resistance
   */
  static getRequiredPassportFields() {
    return [
      'passport_version', 'passport_id', 'task_id', 'canonical_hash', 'version',
      'origin_host', 'target_host', 'worker_class', 'runtime_version', 'created_at',
      'expires_at', 'nonce', 'authorizing_signature', 'issuer_id', 'permission_mask',
      'sandbox_mode', 'isolation_level', 'allow_network', 'allow_spend', 'max_memory_mb',
      'max_cpu_percent', 'max_duration_ms', 'allowed_paths', 'read_only_paths', 'evidence_hash',
      'deliverable_hashes', 'parent_task_id', 'root_goal_id', 'human_gate_required', 'human_gate_state',
      'audit_ledger_id', 'checkpoint_ref', 'writer_id', 'verifier_id', 'transport_protocol',
      'cipher_suite', 'encryption_algorithm', 'certificate_fingerprint', 'appeal_budget', 'retry_budget',
      'fallback_route', 'integrity_seal'
    ];
  }

  static verifyPassport(passport, secretKey = 'COURIER_MASTER_SECRET') {
    const required = BorderAndCustomsEngine.getRequiredPassportFields();
    
    // 1. Check all 42 fields present
    const missing = required.filter(f => passport[f] === undefined || passport[f] === null);
    if (missing.length > 0) {
      return { valid: false, code: 'PASSPORT_INCOMPLETE', missing_fields: missing, count_missing: missing.length };
    }

    // 2. Version check
    if (passport.passport_version !== '2.0') {
      return { valid: false, code: 'PASSPORT_VERSION_UNSUPPORTED', reason: `Expected 2.0, got ${passport.passport_version}` };
    }

    // 3. Expiration / Clock skew check
    const now = Date.now();
    const created = new Date(passport.created_at).getTime();
    const expires = new Date(passport.expires_at).getTime();
    if (isNaN(created) || isNaN(expires)) {
      return { valid: false, code: 'PASSPORT_TIMESTAMP_CORRUPT' };
    }
    if (now > expires) {
      return { valid: false, code: 'PASSPORT_EXPIRED', reason: 'Passport has expired.' };
    }
    if (created > now + 60000) { // More than 1 min in the future
      return { valid: false, code: 'PASSPORT_CLOCK_SKEW_EXCESSIVE', reason: 'Created timestamp in the future.' };
    }

    // 4. Signature check
    const dataToSign = `${passport.passport_id}:${passport.task_id}:${passport.canonical_hash}:${passport.nonce}:${passport.expires_at}`;
    const expectedSig = crypto.createHmac('sha256', secretKey).update(dataToSign).digest('hex');
    if (passport.authorizing_signature !== expectedSig) {
      return { valid: false, code: 'PASSPORT_SIGNATURE_INVALID', reason: 'HMAC signature does not match.' };
    }

    return { valid: true, code: 'PASSPORT_VERIFIED', reason: 'All 42 fields present and signature valid.' };
  }

  /**
   * CAMPAIGN 021: Prose-as-Proof Rejection
   */
  static evaluateProofArtifact(submission) {
    if (!submission || typeof submission !== 'object') {
      return { valid: false, code: 'SUBMISSION_EMPTY', reason: 'Submission must be a structured evidence object.' };
    }

    // Detect prose-only submissions
    const hasMachineEvidence = Boolean(
      submission.exit_code !== undefined ||
      submission.test_results_json ||
      submission.artifact_sha256 ||
      submission.execution_ledger_ref
    );

    if (!hasMachineEvidence) {
      return {
        valid: false,
        code: 'PROSE_REJECTED_MACHINE_PROOF_REQUIRED',
        reason: 'Unsubstantiated text or narrative claims cannot be accepted as proof. Durable machine-verifiable evidence required.'
      };
    }

    if (submission.exit_code !== 0) {
      return {
        valid: false,
        code: 'NON_ZERO_EXIT_CODE',
        reason: `Process exited with code ${submission.exit_code}; cannot be accepted as pass.`
      };
    }

    return { valid: true, code: 'MACHINE_PROOF_ACCEPTED', reason: 'Machine-verifiable evidence verified.' };
  }

  /**
   * CAMPAIGN 022: Test-Weakening Detection
   */
  static inspectTestChanges(diffContent) {
    const weakeningPatterns = [
      /\/\/\s*expect\(/,               // Commented out assertions
      /\/\/\s*assert\./,               // Commented out node assert
      /\.skip\(/,                      // test.skip or it.skip
      /it\.only\(/,                     // it.only omitting test suite
      /expect\(true\)\.toBe\(true\)/,  // Trivial tautological replacement
      /return;\s*\/\/\s*bypass/i       // Early return bypass
    ];

    for (const pat of weakeningPatterns) {
      if (pat.test(diffContent)) {
        return {
          weakened: true,
          code: 'TEST_WEAKENING_DETECTED',
          pattern: pat.toString(),
          reason: `Diff contains evidence of assertion skipping, comment-out, or weakening: ${pat}`
        };
      }
    }

    return {
      weakened: false,
      code: 'TESTS_PRESERVED',
      reason: 'No test-weakening signatures detected in diff.'
    };
  }

  /**
   * CAMPAIGN 023: False Terminal Satisfaction Invariant
   */
  static verifyTerminalSatisfaction(claim) {
    if (!claim.deliverables || claim.deliverables.length === 0) {
      return { satisfied: false, code: 'NO_DELIVERABLES', reason: 'Terminal success claimed with zero deliverables.' };
    }

    for (const d of claim.deliverables) {
      if (!d.exists_on_disk || !d.sha256) {
        return {
          satisfied: false,
          code: 'DELIVERABLE_MISSING_OR_CORRUPT',
          reason: `Deliverable ${d.path} is missing from disk or lacks SHA256.`
        };
      }
    }

    if (claim.failed_tests && claim.failed_tests > 0) {
      return {
        satisfied: false,
        code: 'TESTS_FAILED',
        reason: `Terminal success claimed despite ${claim.failed_tests} failing tests.`
      };
    }

    if (claim.pending_children && claim.pending_children > 0) {
      return {
        satisfied: false,
        code: 'PENDING_CHILDREN_UNRESOLVED',
        reason: `Terminal success claimed with ${claim.pending_children} child tasks still pending.`
      };
    }

    return { satisfied: true, code: 'TERMINAL_SATISFACTION_PROVEN', reason: 'All deliverables exist and tests passed cleanly.' };
  }
}

module.exports = { BorderAndCustomsEngine };
