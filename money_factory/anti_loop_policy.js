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

  static validateExperimentDispatch({
    opportunity_id,
    prior_experiments = [],
    previous_experiments = [],
    proposed_experiment,
    hypothesis,
    signal_to_measure,
    new_angle_or_evidence = false
  }) {
    if (!opportunity_id) {
      throw new Error('[ANTI_LOOP_ERROR] opportunity_id is required');
    }

    const effectivePriors = (prior_experiments && prior_experiments.length > 0) ? prior_experiments : previous_experiments;
    const effectiveHypothesis = proposed_experiment ? proposed_experiment.hypothesis : hypothesis;
    const effectiveSignal = proposed_experiment ? proposed_experiment.signal_to_measure : (signal_to_measure || 'EXTERNAL_DEMAND_SIGNAL');

    if (!effectiveHypothesis) {
      throw new Error('[ANTI_LOOP_ERROR] hypothesis or proposed_experiment is required');
    }

    if (new_angle_or_evidence) {
      return {
        allowed: true,
        is_zero_info_loop: false,
        reason: 'Valid experiment proposal: introduces new angle, hypothesis, or external evidence vector.'
      };
    }

    // Check for duplicate/repeated zero-information experiments
    for (const prior of effectivePriors) {
      const priorMatchesHypothesis = (prior.hypothesis === effectiveHypothesis);
      const priorYieldedEvidence = (prior.new_external_evidence_found === true || (prior.evidence_yielded && prior.evidence_yielded > 0));

      if (priorMatchesHypothesis && !priorYieldedEvidence) {
        return {
          allowed: false,
          is_zero_info_loop: true,
          reason: `ANTI_LOOP_VIOLATION: Repeated zero-information experiment blocked for ${opportunity_id}. Prior test yielded no external evidence.`
        };
      }
    }

    return {
      allowed: true,
      is_zero_info_loop: false,
      reason: 'Valid non-redundant experiment proposal.'
    };
  }

  static evaluateStagnantOpportunity({
    opportunity_id = 'UNKNOWN',
    failed_experiment_count = 0,
    consecutive_zero_info_runs = 0,
    has_external_evidence = false,
    lifecycle = 'ACTIVE',
    days_in_lifecycle = 0
  }) {
    const runs = Math.max(Number(failed_experiment_count) || 0, Number(consecutive_zero_info_runs) || 0);

    if (runs >= 2 && !has_external_evidence) {
      return {
        is_stagnant: true,
        should_retire: true,
        recommended_action: 'DEMOTE_OR_KILL',
        reason: `Opportunity ${opportunity_id} is stagnant after ${runs} zero-evidence tests. Demote to SEED, Mutate, or Kill.`
      };
    }

    return {
      is_stagnant: false,
      should_retire: false,
      recommended_action: 'CONTINUE_ACTIVE',
      reason: 'Opportunity active within acceptable trial bounds.'
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
