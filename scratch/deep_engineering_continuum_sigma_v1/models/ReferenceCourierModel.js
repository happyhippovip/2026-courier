// Independent Reference Courier Oracle Model — Sigma V1
// Invariant: Completely independent reference specification for differential verification.
// Does NOT use implementation shortcuts or duplicate code lines.

class ReferenceCourierModel {
  constructor() {
    this.completedTasks = new Set();
    this.activeDispatches = new Map(); // taskId -> workerId
    this.heldPaths = new Map(); // normalized path -> taskId
    this.uncertainFences = new Set();
    this.settledOpportunities = new Set();
  }

  // 1. may_dispatch oracle
  may_dispatch({ task_id, worker_id, is_uncertain = false, has_active_lease = false }) {
    if (!task_id || !worker_id) {
      return { allowed: false, reason: 'MISSING_IDENTIFIER' };
    }
    if (this.uncertainFences.has(task_id) || is_uncertain) {
      return { allowed: false, reason: 'EXECUTION_UNCERTAIN_BLOCKED' };
    }
    if (this.completedTasks.has(task_id)) {
      return { allowed: false, reason: 'ALREADY_COMPLETED' };
    }
    if (this.activeDispatches.has(task_id) || has_active_lease) {
      return { allowed: false, reason: 'ALREADY_DISPATCHED' };
    }
    return { allowed: true, reason: 'DISPATCH_PERMITTED' };
  }

  // 2. may_retry oracle
  may_retry({ task_id, exit_code, has_durable_proof_of_non_effect = false }) {
    if (this.uncertainFences.has(task_id)) {
      return { allowed: false, reason: 'CANNOT_RETRY_UNCERTAIN_STATE' };
    }
    // If exit code is non-zero AND we have proof that partial side effects were NOT committed:
    if (exit_code !== 0 && has_durable_proof_of_non_effect) {
      return { allowed: true, reason: 'CLEAN_FAILURE_RETRY_PERMITTED' };
    }
    if (exit_code !== 0 && !has_durable_proof_of_non_effect) {
      return { allowed: false, reason: 'DIRTY_FAILURE_UNCERTAIN_SIDE_EFFECTS' };
    }
    return { allowed: false, reason: 'SUCCESS_DOES_NOT_REQUIRE_RETRY' };
  }

  // 3. resource_conflict oracle
  resource_conflict(pathA, pathB) {
    const normA = pathA.replace(/\\/g, '/').toLowerCase().replace(/\/+$/, '');
    const normB = pathB.replace(/\\/g, '/').toLowerCase().replace(/\/+$/, '');
    if (normA === normB) return true;
    if (normA.startsWith(normB + '/')) return true;
    if (normB.startsWith(normA + '/')) return true;
    return false;
  }

  // 4. process_identity oracle
  process_identity({ recorded_pid, recorded_start_ms, current_pid, current_start_ms }) {
    if (recorded_pid !== current_pid) return { match: false, reason: 'PID_CHANGED' };
    if (Math.abs(recorded_start_ms - current_start_ms) > 1000) {
      return { match: false, reason: 'PID_RECYCLED_DIFFERENT_START_TIME' };
    }
    return { match: true, reason: 'IDENTITY_CONFIRMED' };
  }

  // 5. approval_valid oracle
  approval_valid({ token, required_role = 'CHIEF', requested_amount_eur = 0 }) {
    if (!token || !token.signature || !token.expires_at_ms) {
      return { valid: false, reason: 'MALFORMED_TOKEN' };
    }
    if (Date.now() > token.expires_at_ms) {
      return { valid: false, reason: 'TOKEN_EXPIRED' };
    }
    if (requested_amount_eur > 0 && token.max_spend_eur < requested_amount_eur) {
      return { valid: false, reason: 'INSUFFICIENT_SPEND_LIMIT' };
    }
    if (token.role !== required_role && token.role !== 'HUMAN_ADMIN') {
      return { valid: false, reason: 'ROLE_MISMATCH' };
    }
    return { valid: true, reason: 'APPROVAL_VALID' };
  }

  // 6. result_valid oracle
  result_valid({ task_id, artifacts = [], exit_code = 0, checksum_map = {} }) {
    if (exit_code !== 0) return { valid: false, reason: 'NON_ZERO_EXIT_CODE' };
    if (!Array.isArray(artifacts) || artifacts.length === 0) {
      return { valid: false, reason: 'MISSING_ARTIFACTS' };
    }
    for (const art of artifacts) {
      if (!checksum_map[art]) {
        return { valid: false, reason: `MISSING_CHECKSUM_FOR_${art}` };
      }
    }
    return { valid: true, reason: 'RESULT_VALID' };
  }

  // 7. goal_satisfied oracle
  goal_satisfied({ goal_id, required_evidences = [], produced_evidences = [] }) {
    if (!required_evidences || required_evidences.length === 0) {
      return { satisfied: false, reason: 'NO_SUCCESS_CRITERIA_DEFINED' };
    }
    const producedSet = new Set(produced_evidences.map(e => typeof e === 'string' ? e : e.id));
    const missing = required_evidences.filter(req => !producedSet.has(req));
    if (missing.length > 0) {
      return { satisfied: false, missing_evidences: missing, reason: 'PARTIAL_EVIDENCE' };
    }
    return { satisfied: true, reason: 'ALL_CRITERIA_VERIFIED' };
  }
}

module.exports = {
  ReferenceCourierModel
};
