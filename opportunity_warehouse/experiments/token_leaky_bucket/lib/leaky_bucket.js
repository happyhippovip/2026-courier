/**
 * Context Window Token Leaky-Bucket Rate Limiter & Backpressure Regulator
 * Implements continuous virtual-time leaky bucket algorithm for LLM token rate regulation,
 * smoothing bursty agent outputs, estimating backpressure delays, and preventing 429 quota exhaustion.
 */

class TokenLeakyBucket {
  constructor(options = {}) {
    this.capacity = options.capacity || 1000; // max burst tokens allowed in bucket
    this.leakRate = options.leakRate || 200; // tokens leaked per second
    this.water = 0; // current fill level (tokens awaiting leak)
    this.lastLeakTime = options.startTime || Date.now();
    this.totalConsumed = 0;
    this.totalRejected = 0;
  }

  leak(currentTime = Date.now()) {
    if (currentTime <= this.lastLeakTime) return;
    const elapsedSec = (currentTime - this.lastLeakTime) / 1000;
    const leakedTokens = elapsedSec * this.leakRate;
    this.water = Math.max(0, this.water - leakedTokens);
    this.lastLeakTime = currentTime;
  }

  tryConsume(tokens, currentTime = Date.now()) {
    this.leak(currentTime);

    if (this.water + tokens <= this.capacity) {
      this.water += tokens;
      this.totalConsumed += tokens;
      return {
        allowed: true,
        tokensRequested: tokens,
        currentWater: Number(this.water.toFixed(2)),
        waitMs: 0
      };
    } else {
      const excess = (this.water + tokens) - this.capacity;
      const waitMs = Math.ceil((excess / this.leakRate) * 1000);
      this.totalRejected++;
      return {
        allowed: false,
        tokensRequested: tokens,
        currentWater: Number(this.water.toFixed(2)),
        waitMs
      };
    }
  }

  getFillPercentage(currentTime = Date.now()) {
    this.leak(currentTime);
    return Number(((this.water / this.capacity) * 100).toFixed(2));
  }
}

module.exports = { TokenLeakyBucket };
