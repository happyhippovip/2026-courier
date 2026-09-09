// Money Scoring Layer — Deterministic Economic Valuation
// Concept:
// Numerator: Revenue Probability * Expected Profit * Automation * Speed * Distribution Fit * Evidence
// Denominator: Cash Required * Agent Time * Human Work * Risk
//
// Invariant: Do NOT treat scalar score as truth. Store component evidence and confidence alongside it.

class MoneyScorer {
  static computeSpeedMultiplier(timeToFirstEuroDays) {
    if (timeToFirstEuroDays === null || timeToFirstEuroDays === undefined || timeToFirstEuroDays === 'UNKNOWN') {
      return 0.5;
    }
    const days = Number(timeToFirstEuroDays);
    if (isNaN(days) || days > 365) return 0.5;
    if (days <= 3) return 2.0;    // Hyper-immediate cash
    if (days <= 7) return 1.6;    // Within this week (NOW horizon)
    if (days <= 14) return 1.3;   // Rapid 2-week cycle
    if (days <= 30) return 1.1;   // Month cycle (30D horizon)
    if (days <= 90) return 0.9;   // Quarter cycle
    return 0.7;                   // Year cycle
  }

  static parseNumeric(val, fallback = 0) {
    if (val === null || val === undefined || val === 'UNKNOWN') return fallback;
    const num = Number(val);
    return isNaN(num) ? fallback : num;
  }

  static computeScore(opp) {
    // 1. Extract inputs with UNKNOWN-safe parsing
    const revProb = Math.max(0.01, Math.min(1.0, this.parseNumeric(opp.revenue_probability, 0.1)));
    const expectedProfit = Math.max(0, this.parseNumeric(opp.expected_profit_eur, 0));
    const automation = Math.max(0.05, Math.min(1.0, this.parseNumeric(opp.automation_score, 0.5)));
    const speed = this.computeSpeedMultiplier(opp.time_to_first_euro);
    const distribution = Math.max(0.05, Math.min(1.0, this.parseNumeric(opp.distribution_fit, 0.5)));
    const evidence = Math.max(0.05, Math.min(1.0, this.parseNumeric(opp.evidence_score, 0.1)));

    // Denominator factors
    const cashReq = Math.max(1.0, this.parseNumeric(opp.capital_required_eur, 0));
    const agentHours = Math.max(0.5, this.parseNumeric(opp.agent_hours_estimate, 1.0));
    const humanMinutes = Math.max(1.0, this.parseNumeric(opp.human_minutes_estimate, 30.0));
    const risk = Math.max(0.1, Math.min(1.0, this.parseNumeric(opp.risk_score, 0.5)));

    // Numerator & Denominator
    const numerator = revProb * expectedProfit * automation * speed * distribution * evidence;
    const denominator = cashReq * agentHours * (humanMinutes / 60.0) * risk;

    const rawScore = denominator > 0 ? (numerator / denominator) : 0;
    const scalarScore = parseFloat(rawScore.toFixed(2));

    // Evidence and confidence evaluation
    const confidence = this.parseNumeric(opp.confidence, 0.5);
    const hasEmpiricalEvidence = opp.evidence_score && opp.evidence_score !== 'UNKNOWN' && Number(opp.evidence_score) >= 0.5;

    return {
      scalar_score: scalarScore,
      confidence: confidence,
      evidence_score: opp.evidence_score === 'UNKNOWN' ? 'UNKNOWN' : evidence,
      speed_multiplier: speed,
      components: {
        revenue_probability: revProb,
        expected_profit_eur: expectedProfit,
        automation_score: automation,
        speed_multiplier: speed,
        distribution_fit: distribution,
        evidence_score: evidence,
        capital_required_eur: cashReq,
        agent_hours_estimate: agentHours,
        human_hours_estimate: parseFloat((humanMinutes / 60.0).toFixed(2)),
        risk_score: risk
      },
      evidence_breakdown: {
        trend_evidence: opp.trend_evidence || 'UNKNOWN',
        source_evidence: opp.source_evidence || 'UNKNOWN',
        channel_fit: opp.channel_fit || 'UNKNOWN',
        is_empirically_verified: Boolean(hasEmpiricalEvidence)
      }
    };
  }
}

module.exports = {
  MoneyScorer
};
