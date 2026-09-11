/**
 * Sliding Window HyperLogLog Estimator
 * Maintains distinct token cardinality estimation over a dynamic time-decaying
 * sliding window W. Uses monotonic timestamped register queues to guarantee bounded
 * memory O(m log W) while ensuring exact expiration of historical tokens.
 */

const crypto = require('crypto');

class SlidingWindowHLL {
  constructor(precision = 6, windowSize = 100) {
    this.p = precision;
    this.m = 1 << precision; // 64 registers for p=6
    this.windowSize = windowSize;
    // Each bucket stores an array of { rho, timestamp }, maintained in strictly decreasing rho
    // and strictly increasing timestamp order.
    this.registers = Array.from({ length: this.m }, () => []);
    this.alphaM = this._computeAlpha(this.m);
  }

  _computeAlpha(m) {
    if (m === 16) return 0.673;
    if (m === 32) return 0.697;
    if (m === 64) return 0.709;
    return 0.7213 / (1 + 1.079 / m);
  }

  _hash(val) {
    const hash = crypto.createHash('sha256').update(String(val)).digest();
    return hash.readUInt32BE(0);
  }

  _rho(w) {
    // Number of leading zeros + 1 in the remaining 32-p bits
    const mask = 0xFFFFFFFF >>> this.p;
    const remaining = w & mask;
    if (remaining === 0) return 32 - this.p;
    return Math.clz32(remaining) - this.p + 1;
  }

  add(item, timestamp) {
    const h = this._hash(item);
    const bucket = h >>> (32 - this.p);
    const rho = this._rho(h);

    const list = this.registers[bucket];

    // Monotonic pruning invariant:
    // If an older entry has rho <= new rho, it can never become the maximum
    // while the new entry is alive, because new entry expires LATER and has higher/equal rho.
    // Therefore, remove any entries with rho <= new rho.
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].rho <= rho) {
        list.splice(i, 1);
      }
    }

    list.push({ rho, timestamp });
  }

  expire(currentTime) {
    const threshold = currentTime - this.windowSize;
    let prunedCount = 0;
    for (let i = 0; i < this.m; i++) {
      const list = this.registers[i];
      const initialLen = list.length;
      this.registers[i] = list.filter(entry => entry.timestamp > threshold);
      prunedCount += (initialLen - this.registers[i].length);
    }
    return prunedCount;
  }

  estimate(currentTime) {
    this.expire(currentTime);

    let sum = 0;
    let emptyRegisters = 0;

    for (let i = 0; i < this.m; i++) {
      const list = this.registers[i];
      const currentRho = list.length > 0 ? list[0].rho : 0;
      if (currentRho === 0) {
        emptyRegisters++;
      }
      sum += Math.pow(2, -currentRho);
    }

    let rawEstimate = (this.alphaM * this.m * this.m) / sum;

    // Small range linear counting correction
    if (rawEstimate <= 2.5 * this.m && emptyRegisters > 0) {
      return Math.round(this.m * Math.log(this.m / emptyRegisters));
    }

    return Math.round(rawEstimate);
  }

  getMemoryFootprint() {
    let totalEntries = 0;
    for (let i = 0; i < this.m; i++) {
      totalEntries += this.registers[i].length;
    }
    return {
      registers: this.m,
      totalEntries,
      avgEntriesPerRegister: totalEntries / this.m
    };
  }
}

module.exports = { SlidingWindowHLL };
