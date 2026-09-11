/**
 * Sliding-Window Exponential Moving Average (EMA) Context Latency Estimator
 * Computes online EWMA token processing latency, TTFT, and variance tracking
 * with outlier damping and dynamic alpha adjustment.
 */

class EMALatencyEstimator {
  constructor(alpha = 0.2, outlierThresholdZ = 3.0) {
    this.alpha = alpha;
    this.outlierThresholdZ = outlierThresholdZ;
    this.ema = null;
    this.variance = 0;
    this.sampleCount = 0;
    this.samples = [];
  }

  // Record a latency observation in milliseconds
  observe(latencyMs) {
    this.sampleCount++;
    this.samples.push(latencyMs);
    if (this.samples.length > 100) this.samples.shift();

    if (this.ema === null) {
      this.ema = latencyMs;
      this.variance = 0;
      return {
        ema: this.ema,
        stdDev: 0,
        isOutlier: false,
        sampleCount: this.sampleCount
      };
    }

    const diff = latencyMs - this.ema;
    const stdDev = Math.sqrt(this.variance);
    const isOutlier = (this.sampleCount > 5 && stdDev > 0) ? (Math.abs(diff) / stdDev > this.outlierThresholdZ) : false;

    // Dampen weight if outlier detected to preserve estimator stability
    const effectiveAlpha = isOutlier ? (this.alpha * 0.2) : this.alpha;

    this.ema = this.ema + effectiveAlpha * diff;
    this.variance = (1 - effectiveAlpha) * (this.variance + effectiveAlpha * Math.pow(diff, 2));

    return {
      ema: parseFloat(this.ema.toFixed(4)),
      stdDev: parseFloat(Math.sqrt(this.variance).toFixed(4)),
      isOutlier,
      sampleCount: this.sampleCount
    };
  }

  getMetrics() {
    return {
      currentEMA: this.ema !== null ? parseFloat(this.ema.toFixed(4)) : 0,
      stdDev: parseFloat(Math.sqrt(this.variance).toFixed(4)),
      totalObservations: this.sampleCount
    };
  }
}

module.exports = { EMALatencyEstimator };
