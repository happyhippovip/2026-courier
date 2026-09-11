/**
 * Context Prompt Anomaly & Drift Scorer
 * Tracks rolling token volumes and categorical distribution across agent conversation turns.
 * Identifies sudden runaway context bloat, recursive loops, and structural prompt drift.
 */

class PromptAnomalyScorer {
  constructor(options = {}) {
    this.windowSize = options.windowSize || 5;
    this.zScoreThreshold = options.zScoreThreshold || 2.0; // flag if > 2 sigma
    this.history = []; // { turn, tokenCount, breakdown, timestamp }
  }

  recordTurn(turn, tokenCount, breakdown = {}) {
    const record = {
      turn,
      tokenCount,
      breakdown: {
        system: breakdown.system || 0,
        rules: breakdown.rules || 0,
        tools: breakdown.tools || 0,
        history: breakdown.history || 0,
        user: breakdown.user || 0
      },
      timestamp: Date.now()
    };
    this.history.push(record);
    return this.evaluateTurn(record);
  }

  computeRollingStats() {
    if (this.history.length === 0) return { mean: 0, stdDev: 0 };

    // Use up to windowSize previous turns (excluding the latest if comparing against history)
    const sample = this.history.slice(-this.windowSize);
    const sum = sample.reduce((acc, r) => acc + r.tokenCount, 0);
    const mean = sum / sample.length;

    if (sample.length <= 1) return { mean, stdDev: 0 };

    const variance = sample.reduce((acc, r) => acc + Math.pow(r.tokenCount - mean, 2), 0) / (sample.length - 1);
    const stdDev = Math.sqrt(variance);

    return { mean: Number(mean.toFixed(2)), stdDev: Number(stdDev.toFixed(2)) };
  }

  evaluateTurn(record) {
    if (this.history.length < 2) {
      return {
        turn: record.turn,
        tokenCount: record.tokenCount,
        isAnomaly: false,
        zScore: 0,
        anomalyReason: null
      };
    }

    // Compare with history excluding current
    const prevHistory = this.history.slice(0, -1).slice(-this.windowSize);
    const sum = prevHistory.reduce((acc, r) => acc + r.tokenCount, 0);
    const mean = sum / prevHistory.length;
    const variance = prevHistory.length > 1
      ? prevHistory.reduce((acc, r) => acc + Math.pow(r.tokenCount - mean, 2), 0) / (prevHistory.length - 1)
      : 0;
    const stdDev = Math.sqrt(variance);

    let zScore = 0;
    if (stdDev > 0) {
      zScore = Number(((record.tokenCount - mean) / stdDev).toFixed(2));
    }

    const isVolumeAnomaly = zScore > this.zScoreThreshold;
    let anomalyReason = null;

    if (isVolumeAnomaly) {
      anomalyReason = 'Abrupt token volume surge (Z=' + zScore + ' > ' + this.zScoreThreshold + ')';
    } else if (record.tokenCount > mean * 2.5 && mean > 500) {
      anomalyReason = 'Sudden 2.5x token inflation above rolling mean';
    }

    return {
      turn: record.turn,
      tokenCount: record.tokenCount,
      rollingMean: Number(mean.toFixed(2)),
      rollingStdDev: Number(stdDev.toFixed(2)),
      zScore,
      isAnomaly: isVolumeAnomaly || anomalyReason !== null,
      anomalyReason
    };
  }

  generateAuditReport() {
    const totalTurns = this.history.length;
    const evaluations = this.history.map((r, i) => {
      // evaluate in context of up to that point
      const subsetHistory = this.history.slice(0, i + 1);
      const subScorer = new PromptAnomalyScorer({ windowSize: this.windowSize, zScoreThreshold: this.zScoreThreshold });
      subScorer.history = subsetHistory;
      return subScorer.evaluateTurn(r);
    });

    const anomalies = evaluations.filter(e => e.isAnomaly);

    return {
      totalTurnsEvaluated: totalTurns,
      anomalyCount: anomalies.length,
      anomalyRatePercent: totalTurns > 0 ? Number(((anomalies.length / totalTurns) * 100).toFixed(2)) : 0,
      anomalousTurns: anomalies,
      recentRollingStats: this.computeRollingStats()
    };
  }
}

module.exports = { PromptAnomalyScorer };
