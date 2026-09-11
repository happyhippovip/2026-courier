/**
 * BFT Shard Adaptive Pacemaker Consensus Engine
 * Dynamically adjusts round timeouts based on EWMA round commit latencies and exponential backoff on timeouts.
 */

class BFTShardAdaptivePacemakerEngine {
  constructor(options = {}) {
    this.minTimeoutMs = options.minTimeoutMs || 500;
    this.maxTimeoutMs = options.maxTimeoutMs || 10000;
    this.alpha = options.alpha || 0.2; // EWMA smoothing factor
    this.currentTimeoutMs = options.initialTimeoutMs || 1000;
    this.estimatedRoundLatency = options.initialLatencyMs || Math.round(this.currentTimeoutMs / 2);
    this.currentRound = 0;
    this.consecutiveTimeouts = 0;
    this.history = [];
  }

  recordRoundCommit(round, latencyMs) {
    this.currentRound = round;
    this.consecutiveTimeouts = 0;

    // Update EWMA round latency
    this.estimatedRoundLatency = (1 - this.alpha) * this.estimatedRoundLatency + this.alpha * latencyMs;

    // Adaptive timeout: 2x smoothed latency bounded by min and max
    const targetTimeout = Math.max(this.minTimeoutMs, Math.min(this.maxTimeoutMs, Math.round(this.estimatedRoundLatency * 2)));
    this.currentTimeoutMs = targetTimeout;

    const entry = {
      round: round,
      event: 'ROUND_COMMIT',
      latencyMs: latencyMs,
      estimatedLatency: Math.round(this.estimatedRoundLatency),
      nextTimeoutMs: this.currentTimeoutMs,
      timestamp: new Date().toISOString()
    };
    this.history.push(entry);
    return entry;
  }

  recordRoundTimeout(round) {
    this.currentRound = round;
    this.consecutiveTimeouts++;

    // Exponential backoff
    this.currentTimeoutMs = Math.min(this.maxTimeoutMs, Math.round(this.currentTimeoutMs * 1.5));

    const entry = {
      round: round,
      event: 'ROUND_TIMEOUT',
      consecutiveTimeouts: this.consecutiveTimeouts,
      nextTimeoutMs: this.currentTimeoutMs,
      timestamp: new Date().toISOString()
    };
    this.history.push(entry);
    return entry;
  }

  getPacemakerStatus() {
    return {
      currentRound: this.currentRound,
      currentTimeoutMs: this.currentTimeoutMs,
      estimatedRoundLatency: Math.round(this.estimatedRoundLatency),
      consecutiveTimeouts: this.consecutiveTimeouts,
      totalEvents: this.history.length
    };
  }
}

module.exports = { BFTShardAdaptivePacemakerEngine };
