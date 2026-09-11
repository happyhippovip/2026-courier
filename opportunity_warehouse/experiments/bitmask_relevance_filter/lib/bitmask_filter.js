/**
 * Context Window Bit-Vector Dynamic Bitmask Relevance Filter
 * Provides sub-millisecond bit-parallel filtering across thousands of context chunks
 * using SIMD-friendly 64-bit integer bitmasks for instant metadata matching.
 */

class BitmaskRelevanceFilter {
  constructor(tagDefinitions = []) {
    this.tagMap = new Map(); // tagName -> bitPosition (0..63)
    this.nextBit = 0n;

    for (const tag of tagDefinitions) {
      this.registerTag(tag);
    }

    this.items = []; // array of { id, text, mask: BigInt, metadata }
  }

  registerTag(tagName) {
    if (this.tagMap.has(tagName)) {
      return this.tagMap.get(tagName);
    }
    if (this.nextBit >= 64n) {
      throw new Error('Maximum 64 tags supported in 64-bit mask');
    }
    const bitPos = this.nextBit;
    const bitMask = 1n << bitPos;
    this.tagMap.set(tagName, bitMask);
    this.nextBit++;
    return bitMask;
  }

  computeMask(tags) {
    let mask = 0n;
    for (const tag of tags) {
      if (this.tagMap.has(tag)) {
        mask |= this.tagMap.get(tag);
      } else {
        // Automatically register unknown tag if capacity allows
        if (this.nextBit < 64n) {
          mask |= this.registerTag(tag);
        }
      }
    }
    return mask;
  }

  addItem(id, text, tags = [], metadata = {}) {
    const mask = this.computeMask(tags);
    this.items.push({
      id,
      text,
      tags,
      mask,
      metadata
    });
  }

  filter(query = {}) {
    // query: { requireAll: ['tag1'], requireAny: ['tag2'], exclude: ['tag3'] }
    const requireAllMask = query.requireAll ? this.computeMask(query.requireAll) : 0n;
    const requireAnyMask = query.requireAny ? this.computeMask(query.requireAny) : 0n;
    const excludeMask = query.exclude ? this.computeMask(query.exclude) : 0n;

    const matched = [];

    for (let i = 0; i < this.items.length; i++) {
      const item = this.items[i];
      const m = item.mask;

      // Check exclusions (MUST NOT have any excluded bits)
      if (excludeMask > 0n && (m & excludeMask) !== 0n) {
        continue;
      }

      // Check requireAll (MUST have all required bits)
      if (requireAllMask > 0n && (m & requireAllMask) !== requireAllMask) {
        continue;
      }

      // Check requireAny (MUST have at least one bit if specified)
      if (requireAnyMask > 0n && (m & requireAnyMask) === 0n) {
        continue;
      }

      matched.push(item);
    }

    return {
      totalEvaluated: this.items.length,
      matchedCount: matched.length,
      matched
    };
  }

  batchFilterPerformance(query, iterations = 1000) {
    const start = process.hrtime.bigint();
    let count = 0;
    for (let i = 0; i < iterations; i++) {
      const res = this.filter(query);
      count = res.matchedCount;
    }
    const end = process.hrtime.bigint();
    const durationNs = Number(end - start);
    const avgNsPerIteration = durationNs / iterations;

    return {
      iterations,
      matchedCount: count,
      totalDurationMs: Number((durationNs / 1e6).toFixed(3)),
      avgMicrosecondsPerQuery: Number((avgNsPerIteration / 1e3).toFixed(3))
    };
  }
}

module.exports = { BitmaskRelevanceFilter };
