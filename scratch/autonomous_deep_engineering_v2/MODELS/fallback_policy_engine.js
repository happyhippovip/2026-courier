/**
 * FALLBACK POLICY & ADVERSARIAL ENGINE (V2 LAB)
 * 
 * Formal policy enforcing:
 * FALLBACK ONLY WHEN PREVIOUS ATTEMPT DEFINITELY PRODUCED NO EFFECT.
 * If effect is uncertain: BLOCK.
 */

const EFFECT_STATUS = Object.freeze({
  DEFINITE_NO_EFFECT: 'DEFINITE_NO_EFFECT',
  POSSIBLE_EFFECT: 'POSSIBLE_EFFECT',
  DEFINITE_EFFECT: 'DEFINITE_EFFECT',
  UNCERTAIN: 'UNCERTAIN'
});

const FALLBACK_DECISION = Object.freeze({
  ALLOW_FALLBACK: 'ALLOW_FALLBACK',
  BLOCK_FALLBACK: 'BLOCK_FALLBACK',
  BLOCK_EXECUTION_UNCERTAIN: 'BLOCK_EXECUTION_UNCERTAIN',
  HUMAN_GATE_REQUIRED: 'HUMAN_GATE_REQUIRED'
});

class FallbackPolicyEngine {
  /**
   * Evaluates whether a fallback candidate can be dispatched after a prior worker attempt failure.
   */
  static evaluateFallbackEligibility(task, priorAttempt, fallbackQueue = []) {
    if (!task || !priorAttempt) {
      throw new Error('[FALLBACK_ERROR] task and priorAttempt required');
    }

    if (!fallbackQueue || fallbackQueue.length === 0) {
      return {
        decision: FALLBACK_DECISION.BLOCK_FALLBACK,
        effect_status: priorAttempt.effect_status,
        reason: 'No fallback candidates available in queue',
        selected_candidate: null
      };
    }

    const effect = priorAttempt.effect_status;

    // Critical Invariant: If effect is UNCERTAIN or POSSIBLE, fallback is strictly BLOCKED
    if (effect === EFFECT_STATUS.UNCERTAIN || effect === EFFECT_STATUS.POSSIBLE_EFFECT) {
      return {
        decision: FALLBACK_DECISION.BLOCK_EXECUTION_UNCERTAIN,
        effect_status: effect,
        reason: `Prior worker '${priorAttempt.worker_id}' outcome is uncertain. Fallback dispatch forbidden to prevent duplicate side-effects.`,
        selected_candidate: null
      };
    }

    // If effect was definite and completed or partially completed, fallback is forbidden
    if (effect === EFFECT_STATUS.DEFINITE_EFFECT) {
      return {
        decision: FALLBACK_DECISION.BLOCK_FALLBACK,
        effect_status: effect,
        reason: `Prior worker '${priorAttempt.worker_id}' produced definite side effects. Fallback forbidden; requires explicit verification or human decision.`,
        selected_candidate: null
      };
    }

    // Only DEFINITE_NO_EFFECT is permitted to fallback
    if (effect === EFFECT_STATUS.DEFINITE_NO_EFFECT) {
      const candidate = fallbackQueue[0]; // Take highest priority candidate
      return {
        decision: FALLBACK_DECISION.ALLOW_FALLBACK,
        effect_status: effect,
        reason: `Prior attempt '${priorAttempt.attempt_id}' confirmed zero side-effects. Safe to route to fallback candidate '${candidate.worker_id}'.`,
        selected_candidate: candidate
      };
    }

    // Default fail-closed
    return {
      decision: FALLBACK_DECISION.BLOCK_EXECUTION_UNCERTAIN,
      effect_status: EFFECT_STATUS.UNCERTAIN,
      reason: 'Unknown effect status: fail-closed to BLOCK_EXECUTION_UNCERTAIN',
      selected_candidate: null
    };
  }

  /**
   * Flawed reference model (demonstrates the duplicate execution bug)
   * Naively falls back whenever a worker reports an error, ignoring effect uncertainty.
   */
  static flawedNaiveFallback(priorAttempt, fallbackQueue) {
    if (fallbackQueue && fallbackQueue.length > 0) {
      return { decision: 'ALLOW_FALLBACK', selected_candidate: fallbackQueue[0] };
    }
    return { decision: 'NO_CANDIDATE' };
  }
}

module.exports = {
  EFFECT_STATUS,
  FALLBACK_DECISION,
  FallbackPolicyEngine
};
