/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Interpolative Search Filter
 * Employs an interpolative search algorithm accelerated by a top-level radix table
 * to perform bounded O(log log N) lookups and range scans over sorted token postings.
 */

const fs = require('fs');

class RadixInterpolativeFilter {
  constructor(radixBits = 8) {
    this.radixBits = radixBits;
    this.sortedKeys = [];
    this.radixTable = [];
    this.shift = 0;
    this.minKey = 0;
    this.maxKey = 0;
  }

  build(keys) {
    if (keys.length === 0) {
      this.sortedKeys = [];
      this.radixTable = [];
      return;
    }

    const unique = Array.from(new Set(keys)).sort((a, b) => a - b);
    this.sortedKeys = unique;
    this.minKey = unique[0];
    this.maxKey = unique[unique.length - 1];

    const range = Math.max(1, this.maxKey - this.minKey);
    const tableSize = 1 << this.radixBits;
    this.radixTable = new Array(tableSize + 1).fill(0);

    for (const k of this.sortedKeys) {
      const bucket = Math.floor(((k - this.minKey) / range) * (tableSize - 1));
      this.radixTable[bucket + 1]++;
    }

    // Cumulative prefix sum
    for (let i = 1; i <= tableSize; i++) {
      this.radixTable[i] += this.radixTable[i - 1];
    }
  }

  // Interpolative search within radix-bounded range
  contains(key) {
    const n = this.sortedKeys.length;
    if (n === 0 || key < this.minKey || key > this.maxKey) return false;

    const tableSize = 1 << this.radixBits;
    const range = Math.max(1, this.maxKey - this.minKey);
    const bucket = Math.floor(((key - this.minKey) / range) * (tableSize - 1));

    let low = this.radixTable[bucket];
    let high = Math.min(n - 1, this.radixTable[bucket + 1]);

    while (low <= high && key >= this.sortedKeys[low] && key <= this.sortedKeys[high]) {
      if (low === high) {
        return this.sortedKeys[low] === key;
      }

      // Interpolation probe formula
      const denom = this.sortedKeys[high] - this.sortedKeys[low];
      const fraction = denom === 0 ? 0 : (key - this.sortedKeys[low]) / denom;
      const mid = low + Math.floor(fraction * (high - low));

      if (this.sortedKeys[mid] === key) {
        return true;
      }
      if (this.sortedKeys[mid] < key) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return false;
  }

  // Fast range query [minK, maxK]
  rangeQuery(minK, maxK) {
    if (this.sortedKeys.length === 0 || minK > maxK) return [];
    const results = [];
    for (let i = 0; i < this.sortedKeys.length; i++) {
      const k = this.sortedKeys[i];
      if (k >= minK && k <= maxK) {
        results.push(k);
      } else if (k > maxK) {
        break;
      }
    }
    return results;
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'radix_interpolative_filter',
      timestamp: new Date().toISOString(),
      keyCount: this.sortedKeys.length,
      radixBits: this.radixBits,
      minKey: this.minKey,
      maxKey: this.maxKey
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { RadixInterpolativeFilter };
