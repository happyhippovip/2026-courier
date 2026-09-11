/**
 * Context Window Token Counting Bloom Filter Evaluator
 * Supports both token addition and deletion in dynamic sliding context streams.
 * Uses 8-bit saturating counters per slot to prevent counter overflow/underflow.
 */

const crypto = require('crypto');

class CountingBloomFilter {
  constructor(size = 2048, hashCount = 4) {
    this.size = size;
    this.hashCount = hashCount;
    this.counters = new Uint8Array(size); // 8-bit counters (0 to 255)
    this.totalItems = 0;
  }

  _hashes(item) {
    const indices = [];
    for (let i = 0; i < this.hashCount; i++) {
      const h = crypto.createHash('sha256').update(`${i}_${item}`).digest();
      const val = (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
      indices.push(val % this.size);
    }
    return indices;
  }

  add(item) {
    const indices = this._hashes(item);
    for (const idx of indices) {
      if (this.counters[idx] < 255) {
        this.counters[idx]++;
      }
    }
    this.totalItems++;
  }

  remove(item) {
    if (!this.contains(item)) {
      return false; // Item not present
    }
    const indices = this._hashes(item);
    for (const idx of indices) {
      if (this.counters[idx] > 0) {
        this.counters[idx]--;
      }
    }
    this.totalItems--;
    return true;
  }

  contains(item) {
    const indices = this._hashes(item);
    for (const idx of indices) {
      if (this.counters[idx] === 0) {
        return false;
      }
    }
    return true;
  }

  estimateMinCount(item) {
    const indices = this._hashes(item);
    let min = 255;
    for (const idx of indices) {
      if (this.counters[idx] < min) {
        min = this.counters[idx];
      }
    }
    return min;
  }
}

module.exports = { CountingBloomFilter };
