// Cheapest Valid Test Selector & ECONOMIC_TEST_PROPOSAL Generator
// Invariant: Prefer €0 tests, read-only research, existing distribution/assets, reversible actions before spend.

const crypto = require('crypto');

class CheapestTestSelector {
  static createTestProposal({
    opportunity_id,
    hypothesis,
    signal_to_measure,
    success_threshold,
    failure_threshold,
    maximum_duration = '48h',
    cash_required_eur = 0.0,
    agent_time_estimate = 2.0,
    human_minutes_estimate = 15,
    external_action_required = false,
    human_gate_required = false,
    evidence_plan = 'Capture log delta and user confirmation artifact',
    kill_or_promote_rule = 'Promote to PROVING if threshold met within duration; otherwise demote/kill'
  }) {
    if (!opportunity_id || !hypothesis || !signal_to_measure) {
      throw new Error('[TEST_PROPOSAL_ERROR] opportunity_id, hypothesis, and signal_to_measure are required');
    }

    const expId = `EXP-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;

    // Preference enforcement: P0 tests must prefer €0
    const isZeroSpend = (cash_required_eur === 0 || cash_required_eur === 0.0);

    return {
      proposal_type: 'ECONOMIC_TEST_PROPOSAL',
      experiment_id: expId,
      opportunity_id,
      hypothesis,
      signal_to_measure,
      success_threshold,
      failure_threshold,
      maximum_duration,
      cash_required_eur: Number(cash_required_eur) || 0.0,
      is_zero_spend: isZeroSpend,
      agent_time_estimate: Number(agent_time_estimate) || 1.0,
      human_minutes_estimate: Number(human_minutes_estimate) || 0,
      external_action_required: Boolean(external_action_required),
      human_gate_required: Boolean(human_gate_required),
      evidence_plan,
      kill_or_promote_rule,
      created_at: new Date().toISOString(),
      status: 'PROPOSED'
    };
  }

  static selectCheapestTestForOpportunity(opportunity) {
    if (!opportunity) throw new Error('[TEST_PROPOSAL_ERROR] opportunity is required');

    // Default template tailored to opportunity next_test
    const nextTest = opportunity.next_test || 'Evaluate market signal via public repo benchmarks';
    const isHumanGateNeeded = (opportunity.human_gates && opportunity.human_gates.length > 0);

    return this.createTestProposal({
      opportunity_id: opportunity.id,
      hypothesis: `Verification of market intent: ${opportunity.title}`,
      signal_to_measure: 'EXTERNAL_DEMAND_SIGNAL',
      success_threshold: 'At least 1 qualified inbound interaction or 100% test pass without errors',
      failure_threshold: 'Zero organic interest or technical blockers in baseline',
      maximum_duration: '48h',
      cash_required_eur: 0.0, // Strictly €0 P0 preference
      agent_time_estimate: opportunity.agent_hours_estimate ? Math.min(opportunity.agent_hours_estimate, 4.0) : 2.0,
      human_minutes_estimate: opportunity.human_minutes_estimate ? Math.min(opportunity.human_minutes_estimate, 30) : 15,
      external_action_required: isHumanGateNeeded,
      human_gate_required: isHumanGateNeeded,
      evidence_plan: `Execute '${nextTest}'. Record logs and output artifact to opportunity_warehouse/evidence/.`,
      kill_or_promote_rule: 'If external evidence acquired, promote to PROVING; if 0 signal after test, demote or kill.'
    });
  }

  static generateTestProposal(opportunity) {
    return this.selectCheapestTestForOpportunity(opportunity);
  }
}

module.exports = {
  CheapestTestSelector
};
