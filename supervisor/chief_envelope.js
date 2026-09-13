// Chief Escalation Envelope — Structured Review Contract
// Invariant: Interface envelope only. No external networking or autonomous dispatch.

const crypto = require('crypto');

class ChiefEscalationEnvelope {
  static createReviewRequest({
    task_id,
    task_version = 1,
    goal_id = null,
    worker_id = null,
    machine_id = 'WINDOWS_LOCAL',
    reason,
    classification,
    evidence_refs = [],
    diagnostic_bundle_ref = null,
    screenshot_ref = null,
    risk = 'HIGH',
    recommended_action = 'HOLD_PENDING_ADVISOR_REVIEW',
    confidence = 0.5
  }) {
    if (!task_id || !reason || !classification) {
      throw new Error('[CHIEF_ENVELOPE_ERROR] task_id, reason, and classification are required');
    }

    const createdAt = new Date().toISOString();
    const requestId = `ESC-CHIEF-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;

    const canonical = {
      escalation_id: requestId,
      task_id,
      task_version,
      machine_id,
      reason,
      classification,
      diagnostic_bundle_ref,
      createdAt
    };
    const fingerprint = crypto.createHash('sha256').update(JSON.stringify(canonical)).digest('hex');

    return {
      escalation_id: requestId,
      envelope_type: 'SUPERVISOR_REVIEW_REQUEST',
      task_id,
      task_version,
      goal_id,
      worker_id,
      machine_id,
      reason,
      classification,
      evidence_refs,
      diagnostic_bundle_ref,
      screenshot_ref: screenshot_ref || 'NONE',
      risk,
      recommended_action,
      confidence,
      created_at: createdAt,
      fingerprint,
      status: 'AWAITING_CHIEF_REVIEW'
    };
  }
}

module.exports = {
  ChiefEscalationEnvelope
};
