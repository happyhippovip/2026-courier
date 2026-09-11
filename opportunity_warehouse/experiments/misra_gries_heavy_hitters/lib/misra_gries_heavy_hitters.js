/**
 * Context Window Token Misra-Gries Heavy Hitters Stream Evaluator
 * Deterministic streaming algorithm that tracks frequent tokens in continuous context window streams.
 * Uses O(k) memory to guarantee that any item appearing > N/k times is retained in the summary,
 * with bounded estimation error <= N/k.
 */

class MisraGriesHeavyHitters {
  constructor(k) {
    if (k < 2) throw new Error('k must be at least 2');
    this.k = k; // Maximum capacity is k - 1
    this.capacity = k - 1;
    this.counters = new Map(); // token -> estimatedCount
    this.totalProcessed = 0;
  }

  processToken(token) {
    this.totalProcessed++;

    if (this.counters.has(token)) {
      this.counters.set(token, this.counters.get(token) + 1);
      return;
    }

    if (this.counters.size < this.capacity) {
      this.counters.set(token, 1);
      return;
    }

    // All k - 1 counters are full: decrement all counters by 1
    for (const [key, count] of this.counters.entries()) {
      if (count === 1) {
        this.counters.delete(key);
      } else {
        this.counters.set(key, count - 1);
      }
    }
  }

  processStream(tokens) {
    for (const token of tokens) {
      this.processToken(token);
    }
  }

  getHeavyHitters() {
    const threshold = this.totalProcessed / this.k;
    const results = [];
    for (const [token, count] of this.counters.entries()) {
      results.push({
        token,
        estimatedCount: count,
        lowerBoundFrequency: count / this.totalProcessed,
        guaranteedExceedsThreshold: count > threshold
      });
    }
    return results.sort((a, b) => b.estimatedCount - a.estimatedCount);
  }

  getEstimatedCount(token) {
    return this.counters.get(token) || 0;
  }

  reset() {
    this.counters.clear();
    this.totalProcessed = 0;
  }
}

module.exports = { MisraGriesHeavyHitters };
