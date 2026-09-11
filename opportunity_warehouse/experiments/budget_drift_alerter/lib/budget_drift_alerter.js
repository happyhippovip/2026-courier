class BudgetDriftAlerter {
  constructor(options = {}) {
    this.maxTokensPerTurn = options.maxTokensPerTurn || 4000;
    this.maxDriftPct = options.maxDriftPct || 25.0;
  }

  evaluateTurn(currentTokens, baselineTokens = null) {
    const exceedsHardBudget = currentTokens > this.maxTokensPerTurn;
    let driftPct = 0;
    let isDriftExceeded = false;

    if (baselineTokens && baselineTokens > 0) {
      driftPct = Number((((currentTokens - baselineTokens) / baselineTokens) * 100).toFixed(2));
      if (driftPct > this.maxDriftPct) {
        isDriftExceeded = true;
      }
    }

    const requiresAlert = exceedsHardBudget || isDriftExceeded;
    let severity = 'OK';
    if (exceedsHardBudget && isDriftExceeded) severity = 'CRITICAL';
    else if (exceedsHardBudget || isDriftExceeded) severity = 'WARNING';

    return {
      currentTokens,
      baselineTokens,
      maxTokensPerTurn: this.maxTokensPerTurn,
      driftPct,
      exceedsHardBudget,
      isDriftExceeded,
      requiresAlert,
      severity,
      alertPayload: requiresAlert ? {
        title: `Token Budget Alert [${severity}]: ${currentTokens} tokens recorded`,
        details: `Hard cap: ${this.maxTokensPerTurn}, Drift: ${driftPct}%`,
        recommendation: 'Run agent-context-trimmer --prune-redundant --ast-level=aggressive to restore budget compliance.'
      } : null
    };
  }
}

module.exports = { BudgetDriftAlerter };
