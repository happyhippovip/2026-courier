/**
 * Context Window Token Conservative Update Count-Min Sketch Evaluator
 * Enhances standard Count-Min Sketch by updating only counters that equal
 * the minimum count among the d hash locations, drastically cutting overestimation bias.
 */

const crypto = require('crypto');

class ConservativeCountMinSketch {
  constructor(width = 256, depth = 5) {
    this.width = width;
    this.depth = depth;
    this.table = Array.from({ length: depth }, () => new Int32Array(width));
    this.totalEvents = 0;
  }

  _hash(item, row) {
    const h = crypto.createHash('sha256').update(`${row}_${item}`).digest();
    const val = (h[0] | (h[1] << 8) | (h[2] << 16) | (h[3] << 24)) >>> 0;
    return val % this.width;
  }

  add(item, count = 1) {
    // 1. Find current minimum across all d rows
    let minVal = Infinity;
    const indices = [];
    for (let r = 0; r < this.depth; r++) {
      const col = this._hash(item, r);
      indices.push(col);
      if (this.table[r][col] < minVal) {
        minVal = this.table[r][col];
      }
    }

    // 2. Only increment counters that equal minVal
    const target = minVal + count;
    for (let r = 0; r < this.depth; r++) {
      const col = indices[r];
      if (this.table[r][col] < target) {
        this.table[r][col] = target;
      }
    }
    this.totalEvents += count;
  }

  estimate(item) {
    let minVal = Infinity;
    for (let r = 0; r < this.depth; r++) {
      const col = this._hash(item, r);
      if (this.table[r][col] < minVal) {
        minVal = this.table[r][col];
      }
    }
    return minVal;
  }
}

module.exports = { ConservativeCountMinSketch };
