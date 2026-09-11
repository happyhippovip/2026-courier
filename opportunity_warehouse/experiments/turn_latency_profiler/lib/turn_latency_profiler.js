/**
 * Multi-Agent Turn Latency & Token Bandwidth Profiler
 * Analyzes time-to-first-token (TTFT), prompt evaluation time, and decode throughput
 * across multi-agent turns, modeling latency savings from context pruning.
 */

class TurnLatencyProfiler {
  constructor(options = {}) {
    this.records = [];
  }

  recordTurn(turnId, inputTokens, outputTokens, ttftMs, totalDurationMs) {
    const decodeTimeMs = Math.max(1, totalDurationMs - ttftMs);
    const decodeTps = outputTokens > 0 ? Number(((outputTokens / (decodeTimeMs / 1000))).toFixed(1)) : 0;
    const prefillTps = inputTokens > 0 ? Number(((inputTokens / (ttftMs / 1000))).toFixed(1)) : 0;

    const record = {
      turnId,
      inputTokens,
      outputTokens,
      ttftMs,
      totalDurationMs,
      decodeTimeMs,
      decodeTps,
      prefillTps,
      prefillLatencyPer1kMs: inputTokens > 0 ? Number(((ttftMs / (inputTokens / 1000))).toFixed(2)) : 0
    };

    this.records.push(record);
    return record;
  }

  estimatePruningSpeedup(pruneRatio = 0.40) {
    if (this.records.length === 0) return null;

    let totalOriginalDuration = 0;
    let totalProjectedDuration = 0;

    const comparisons = this.records.map(r => {
      totalOriginalDuration += r.totalDurationMs;

      // Prefill time scales roughly linearly with input token volume
      const reducedInput = Math.round(r.inputTokens * (1 - pruneRatio));
      const projectedTtftMs = Math.round(r.ttftMs * (1 - pruneRatio * 0.85)); // 85% linear scaling factor
      const projectedTotalMs = projectedTtftMs + r.decodeTimeMs;

      totalProjectedDuration += projectedTotalMs;

      return {
        turnId: r.turnId,
        originalInputTokens: r.inputTokens,
        prunedInputTokens: reducedInput,
        originalTtftMs: r.ttftMs,
        projectedTtftMs,
        ttftReductionPercent: Number((((r.ttftMs - projectedTtftMs) / r.ttftMs) * 100).toFixed(1)),
        originalTotalMs: r.totalDurationMs,
        projectedTotalMs,
        totalSavingsMs: r.totalDurationMs - projectedTotalMs
      };
    });

    const netSpeedupPercent = totalOriginalDuration > 0
      ? Number((((totalOriginalDuration - totalProjectedDuration) / totalOriginalDuration) * 100).toFixed(1))
      : 0;

    return {
      pruneRatio,
      totalOriginalDurationMs: totalOriginalDuration,
      totalProjectedDurationMs: totalProjectedDuration,
      netTimeSavedMs: totalOriginalDuration - totalProjectedDuration,
      netSpeedupPercent,
      turnBreakdowns: comparisons
    };
  }

  generateProfileReport() {
    const count = this.records.length;
    const avgTtft = count > 0 ? Math.round(this.records.reduce((acc, r) => acc + r.ttftMs, 0) / count) : 0;
    const avgDuration = count > 0 ? Math.round(this.records.reduce((acc, r) => acc + r.totalDurationMs, 0) / count) : 0;
    const avgPrefillTps = count > 0 ? Math.round(this.records.reduce((acc, r) => acc + r.prefillTps, 0) / count) : 0;

    const speedupAt40 = this.estimatePruningSpeedup(0.40);

    return {
      totalTurnsProfiled: count,
      averageTtftMs: avgTtft,
      averageDurationMs: avgDuration,
      averagePrefillTps: avgPrefillTps,
      projectedSavingsAt40PercentPrune: speedupAt40,
      records: this.records
    };
  }
}

module.exports = { TurnLatencyProfiler };
