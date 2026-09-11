/**
 * Context Window Token Sparse Distributed Representation (SDR) Matcher
 * Encodes token concepts into sparse binary vectors (n=1024, w=20 active bits, 2% sparsity)
 * providing fault-tolerant semantic overlap matching and union representation.
 */

class SDRTokenMatcher {
  constructor(n = 1024, w = 20) {
    this.n = n;
    this.w = w;
  }

  hash(str, seed) {
    let h = 0x811c9dc5 ^ seed;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return Math.abs(h % this.n);
  }

  // Encode token into sorted set of w active bit indices
  encode(token) {
    const indices = new Set();
    let seed = 0;
    while (indices.size < this.w) {
      indices.add(this.hash(token, seed++));
    }
    return Array.from(indices).sort((a, b) => a - b);
  }

  // Overlap score: number of shared active bits
  computeOverlap(sdrA, sdrB) {
    const setB = new Set(sdrB);
    let overlap = 0;
    for (const bit of sdrA) {
      if (setB.has(bit)) overlap++;
    }
    return overlap;
  }

  // Overlap ratio relative to w
  overlapRatio(sdrA, sdrB) {
    return this.computeOverlap(sdrA, sdrB) / this.w;
  }

  // Corrupt an SDR by flipping k bits to simulate noisy transmission
  corrupt(sdr, flipCount) {
    const corrupted = new Set(sdr);
    // Remove flipCount existing bits
    const arr = Array.from(corrupted);
    for (let i = 0; i < Math.min(flipCount, arr.length); i++) {
      corrupted.delete(arr[i]);
    }
    // Add random new bits
    let seed = 999;
    while (corrupted.size < this.w) {
      corrupted.add(this.hash('noise', seed++));
    }
    return Array.from(corrupted).sort((a, b) => a - b);
  }
}

module.exports = { SDRTokenMatcher };
