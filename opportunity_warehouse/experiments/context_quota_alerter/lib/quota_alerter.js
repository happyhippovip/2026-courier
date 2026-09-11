/**
 * quota_alerter.js - Real-Time Context Token Quota & Cost Alerter Daemon
 * Tracks session token accumulation, evaluates velocity limits, and triggers circuit breakers.
 */
class ContextQuotaAlerter {
  constructor(options = {}) {
    this.maxTokensPerSession = options.maxTokensPerSession || 100000;
    this.warningThresholdRatio = options.warningThresholdRatio || 0.80; // 80% warning
    this.currentTokensAccumulated = 0;
    this.history = [];
    this.isCircuitBreakerTripped = false;
  }

  ingestPromptUsage(tokens, agentId = 'default_agent') {
    const previousTokens = this.currentTokensAccumulated;
    this.currentTokensAccumulated += tokens;

    const ratio = this.currentTokensAccumulated / this.maxTokensPerSession;
    let status = 'NORMAL';

    if (this.currentTokensAccumulated >= this.maxTokensPerSession) {
      status = 'CIRCUIT_BREAKER_TRIPPED';
      this.isCircuitBreakerTripped = true;
    } else if (ratio >= this.warningThresholdRatio) {
      status = 'WARNING_THRESHOLD_EXCEEDED';
    }

    const event = {
      eventId: 'EVT_' + (this.history.length + 1).toString().padStart(3, '0'),
      agentId,
      tokensUsed: tokens,
      cumulativeTokens: this.currentTokensAccumulated,
      maxTokens: this.maxTokensPerSession,
      usageRatio: Number(ratio.toFixed(3)),
      status,
      timestamp: new Date().toISOString()
    };

    this.history.push(event);

    return {
      status,
      isBlocked: this.isCircuitBreakerTripped,
      usageRatio: Number(ratio.toFixed(3)),
      remainingTokens: Math.max(0, this.maxTokensPerSession - this.currentTokensAccumulated),
      event
    };
  }

  resetSession() {
    this.currentTokensAccumulated = 0;
    this.isCircuitBreakerTripped = false;
    this.history = [];
    return { status: 'RESET_SUCCESSFUL', cumulativeTokens: 0 };
  }
}

module.exports = { ContextQuotaAlerter };
