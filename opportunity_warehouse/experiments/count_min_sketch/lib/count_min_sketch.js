/**
 * Streaming Context Token Count-Min Sketch & Heavy Hitter Detector
 * Implements probabilistic sub-linear space frequency estimation (depth d, width w)
 * with conservative updates and min-heap heavy hitter tracking.
 */

class CountMinSketch {
  constructor(depth = 4, width = 256) {
    this.depth = depth;
    this.width = width;
    this.table = Array.from({ length: depth }, () => new Uint32Array(width));
    this.totalCount = 0;
    this.heavyHitters = new Map(); // token -> estimatedCount
  }

  hash(str, seed) {
    let h = 0x811c9dc5 ^ seed;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return Math.abs(h % this.width);
  }

  // Update sketch with conservative update heuristic
  add(token, count = 1) {
    this.totalCount += count;
    const indices = [];
    let minVal = Infinity;

    for (let i = 0; i < this.depth; i++) {
      const idx = this.hash(token, i * 7919);
      indices.push(idx);
      if (this.table[i][idx] < minVal) {
        minVal = this.table[i][idx];
      }
    }

    const newVal = minVal + count;
    for (let i = 0; i < this.depth; i++) {
      if (this.table[i][indices[i]] < newVal) {
        this.table[i][indices[i]] = newVal;
      }
    }

    // Heavy hitter check (e.g. > 2% of total stream)
    if (newVal / this.totalCount > 0.02) {
      this.heavyHitters.set(token, newVal);
    }
  }

  // Estimate frequency
  estimate(token) {
    let minVal = Infinity;
    for (let i = 0; i < this.depth; i++) {
      const idx = this.hash(token, i * 7919);
      if (this.table[i][idx] < minVal) {
        minVal = this.table[i][idx];
      }
    }
    return minVal;
  }
}

module.exports = { CountMinSketch };
