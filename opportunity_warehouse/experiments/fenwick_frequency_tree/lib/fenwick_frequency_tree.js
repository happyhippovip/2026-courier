/**
 * Context Window Token Fenwick Tree (Binary Indexed Tree) Frequency Accumulator
 * Provides O(log N) point updates and prefix frequency sum queries
 * for instantaneous context density and range frequency evaluations.
 */

class FenwickTree {
  constructor(size = 100) {
    this.size = size;
    this.tree = new Float64Array(size + 1); // 1-indexed
  }

  // Add delta to index i (1-indexed)
  update(i, delta) {
    while (i <= this.size) {
      this.tree[i] += delta;
      i += i & (-i);
    }
  }

  // Compute prefix sum from 1 to i
  queryPrefix(i) {
    let sum = 0;
    while (i > 0) {
      sum += this.tree[i];
      i -= i & (-i);
    }
    return sum;
  }

  // Compute range sum [left, right]
  queryRange(left, right) {
    if (left > right) return 0;
    return this.queryPrefix(right) - this.queryPrefix(left - 1);
  }
}

module.exports = { FenwickTree };
