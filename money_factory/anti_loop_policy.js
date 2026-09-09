// Economic Anti-Loop Policy & Truth Firewall
// Invariant:
// After Courier freeze, Courier infrastructure may only be modified when a reproducible Courier defect concretely blocks product/revenue work.
// Prohibits:
// - Endless infrastructure refactoring without product blocking defect
// - Counting synthetic FAST_TEST_MODE signals as real revenue
// - Autonomous engagement farming or bot follow networks
// - Fake accounts / synthetic metrics

const ECONOMIC_LOOP_STAGES = Object.freeze([
  'RESEARCH',
  'OPPORTUNITIES',
  'SCORE',
  'TEST',
  'BUILD',
  'VERIFY',
  'DISTRIBUTE_HUMAN_GATE',
  'REVENUE',
  'LEARN',
  'NEXT_OPPORTUNITY'
]);

class AntiLoopPolicy {
  static validateInfrastructureChangeRequest({
    is_courier_frozen = true,
    has_blocking_defect = false,
    reproducible_test_case = null,
    impacted_opportunity_id = null,
    justification = ''
  }) {
    if (!is_courier_frozen) {
      return { allowed: true, reason: 'Courier not yet frozen; active pre-freeze changes permitted.' };
    }

    if (!has_blocking_defect) {
      return {
        allowed: false,
        reason: 'ANTI_LOOP_VIOLATION: Courier infrastructure changes post-freeze require a concrete blocking defect.'
      };
    }

    if (!reproducible_test_case || typeof reproducible_test_case !== 'string' || reproducible_test_case.trim().length < 10) {
      return {
        allowed: false,
        reason: 'ANTI_LOOP_VIOLATION: Must supply a verifiable, reproducible test case demonstrating the blocking defect.'
      };
    }

    if (!impacted_opportunity_id) {
      return {
        allowed: false,
        reason: 'ANTI_LOOP_VIOLATION: Must explicitly link to the revenue opportunity currently blocked.'
      };
    }

    return {
      allowed: true,
      reason: `Permitted bugfix: defect blocking opportunity ${impacted_opportunity_id} verified with test case.`
    };
  }

  static validateEconomicEvidence({
    evidence_type,
    is_synthetic_test = false,
    external_bank_or_stripe_proof = false,
    engagement_source = 'ORGANIC'
  }) {
    // 1. Synthetic FAST_TEST_MODE can never count as real revenue
    if (is_synthetic_test || evidence_type === 'FAST_TEST_MODE' || evidence_type === 'SYNTHETIC') {
      return {
        is_valid_economic_signal: false,
        classification: 'SYNTHETIC_SIGNAL',
        allowed_for_winner_promotion: false,
        reason: 'FAST_TEST_MODE or synthetic simulation cannot count as empirical market revenue.'
      };
    }

    // 2. Prohibit fake engagement farming
    if (engagement_source === 'BOT_FARM' || engagement_source === 'SYNTHETIC_ENGAGEMENT') {
      return {
        is_valid_economic_signal: false,
        classification: 'FAKE_ENGAGEMENT',
        allowed_for_winner_promotion: false,
        reason: 'Synthetic or automated engagement farming is strictly disallowed by safety policy.'
      };
    }

    // 3. True real revenue requires verifiable receipt / external proof
    if (evidence_type === 'REAL_REVENUE') {
      if (!external_bank_or_stripe_proof) {
        return {
          is_valid_economic_signal: false,
          classification: 'UNCONFIRMED_CLAIM',
          allowed_for_winner_promotion: false,
          reason: 'REAL_REVENUE claims require verifiable external settlement evidence.'
        };
      }
      return {
        is_valid_economic_signal: true,
        classification: 'REAL_REVENUE',
        allowed_for_winner_promotion: true,
        reason: 'Empirically settled revenue verified.'
      };
    }

    return {
      is_valid_economic_signal: true,
      classification: evidence_type || 'LEADING_SIGNAL',
      allowed_for_winner_promotion: false,
      reason: 'Valid leading market indicator, but insufficient for final WINNER state without settled revenue.'
    };
  }

  static validateAccountAction(actionType) {
    const prohibited = ['ACCOUNT_FARMING', 'AUTO_2FA_BYPASS', 'FAKE_IDENTITY_CREATION'];
    if (prohibited.includes(actionType)) {
      throw new Error(`[ANTI_LOOP_VIOLATION] Disallowed autonomous action: ${actionType}`);
    }
    return true;
  }
}

module.exports = {
  ECONOMIC_LOOP_STAGES,
  AntiLoopPolicy
};
