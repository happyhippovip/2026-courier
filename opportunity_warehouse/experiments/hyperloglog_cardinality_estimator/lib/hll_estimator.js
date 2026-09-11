/**
 * Context Window Dynamic HyperLogLog Unique Token Cardinality Estimator
 * Implements the Flajolet et al. HyperLogLog algorithm with linear counting bias correction,
 * tracking token vocabulary diversity and unique identifier saturation in O(1) space.
 */

class HyperLogLogEstimator {
  constructor(precisionBits = 6) {
    this.p = precisionBits; // 6 bits -> m = 64 registers
    this.m = 1 << this.p;
    this.registers = new Uint8Array(this.m);

    // Alpha correction constant
    if (this.m === 16) this.alpha = 0.673;
    else if (this.m === 32) this.alpha = 0.697;
    else if (this.m === 64) this.alpha = 0.709;
    else this.alpha = 0.7213 / (1 + 1.079 / this.m);
  }

  fmix32(h) {
    h ^= h >>> 16;
    h = Math.imul(h, 0x85ebca6b);
    h ^= h >>> 13;
    h = Math.imul(h, 0xc2b2ae35);
    h ^= h >>> 16;
    return (h >>> 0);
  }

  hash(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return this.fmix32(h >>> 0);
  }

  countLeadingZeros(value, maxBits) {
    if (value === 0) return maxBits;
    let zeros = 0;
    for (let i = maxBits - 1; i >= 0; i--) {
      if ((value & (1 << i)) === 0) {
        zeros++;
      } else {
        break;
      }
    }
    return zeros;
  }

  add(token) {
    if (!token) return;
    const tokenStr = String(token);
    const h = this.hash(tokenStr);

    // First p bits determine register index
    const registerIndex = (h >>> (32 - this.p)) & (this.m - 1);
    // Remaining (32 - p) bits
    const remainingBits = 32 - this.p;
    const w = h & ((1 << remainingBits) - 1);

    const rank = this.countLeadingZeros(w, remainingBits) + 1;
    if (rank > this.registers[registerIndex]) {
      this.registers[registerIndex] = rank;
    }
  }

  addTokens(tokens) {
    const list = Array.isArray(tokens) ? tokens : String(tokens).split(/\s+/);
    for (const t of list) {
      if (t) this.add(t);
    }
  }

  estimate() {
    let sum = 0;
    let zeroCount = 0;

    for (let i = 0; i < this.m; i++) {
      const val = this.registers[i];
      sum += Math.pow(2, -val);
      if (val === 0) zeroCount++;
    }

    let rawEstimate = (this.alpha * this.m * this.m) / sum;

    // Small cardinality correction via Linear Counting
    if (rawEstimate <= 2.5 * this.m) {
      if (zeroCount > 0) {
        rawEstimate = this.m * Math.log(this.m / zeroCount);
      }
    }

    return Math.round(rawEstimate);
  }

  merge(other) {
    if (other.m !== this.m) {
      throw new Error('Cannot merge HLL instances with different precision');
    }
    for (let i = 0; i < this.m; i++) {
      if (other.registers[i] > this.registers[i]) {
        this.registers[i] = other.registers[i];
      }
    }
  }

  getStats() {
    return {
      precisionBits: this.p,
      registerCount: this.m,
      estimatedCardinality: this.estimate(),
      theoreticalStandardError: Number((1.04 / Math.sqrt(this.m)).toFixed(4))
    };
  }
}

module.exports = { HyperLogLogEstimator };
