/**
 * Context Window Token Count-Min-Mean Sketch Evaluator
 * Enhances the standard Count-Min sketch by removing noise bias via mean residual subtraction.
 * Computes unbiased frequency estimates by subtracting estimated average row noise.
 */

const crypto = require('crypto');

class CountMinMeanSketch {
  constructor(width = 256, depth = 5) {
    this.width = width;
    this.depth = depth;
    this.table = Array.from({ length: depth }, () => new Int32Array(width));
    this.totalCount = 0;
  }

  _hash(item, row) {
    const h = crypto.createHash('sha256').update(`${row}_${item}`).digest();
    const val = (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
    return val % this.width;
  }

  add(item, count = 1) {
    for (let r = 0; r < this.depth; r++) {
      const col = this._hash(item, r);
      this.table[r][col] += count;
    }
    this.totalCount += count;
  }

  estimate(item) {
    const estimates = [];

    for (let r = 0; r < this.depth; r++) {
      const col = this._hash(item, r);
      const rawCount = this.table[r][col];
      // Expected noise from other elements in the row
      const noise = (this.totalCount - rawCount) / (this.width - 1);
      const unbiasedEstimate = Math.max(0, Math.round(rawCount - noise));
      estimates.push(unbiasedEstimate);
    }

    // Median of estimates across rows
    estimates.sort((a, b) => a - b);
    const mid = Math.floor(estimates.length / 2);
    return estimates[mid];
  }
}

module.exports = { CountMinMeanSketch };
