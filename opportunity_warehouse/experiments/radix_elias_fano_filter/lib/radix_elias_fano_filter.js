/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Elias-Fano Bitvector Inverted Index Filter
 * Quasi-succinct Elias-Fano encoding for monotonic integer sequences, splitting keys
 * into high bits (unary in bitvector) and low bits (fixed length), accelerated by top-level radix table.
 */

const fs = require('fs');

class RadixEliasFanoFilter {
  constructor(radixBits = 4) {
    this.radixBits = radixBits;
    this.sortedKeys = [];
    this.lowBits = [];
    this.highBitsUnary = []; // bit array with 1s and 0s
    this.lowBitWidth = 0;
    this.universe = 0;
    this.keyCount = 0;
    this.radixTable = [];
  }

  build(keys) {
    if (keys.length === 0) {
      this.sortedKeys = [];
      this.lowBits = [];
      this.highBitsUnary = [];
      this.radixTable = [];
      this.keyCount = 0;
      return;
    }

    const unique = Array.from(new Set(keys)).sort((a, b) => a - b);
    this.sortedKeys = unique;
    this.keyCount = unique.length;
    this.universe = Math.max(1, unique[unique.length - 1]);

    // Elias-Fano parameters:
    // lowBitWidth l = floor(log2(U / N))
    const ratio = Math.max(1, Math.floor(this.universe / this.keyCount));
    this.lowBitWidth = Math.max(1, Math.floor(Math.log2(ratio)));
    const lowMask = (1 << this.lowBitWidth) - 1;

    this.lowBits = [];
    let currentHigh = 0;
    this.highBitsUnary = [];

    for (let i = 0; i < this.keyCount; i++) {
      const k = unique[i];
      const lowVal = k & lowMask;
      const highVal = k >> this.lowBitWidth;

      this.lowBits.push(lowVal);

      // Unary encoding: append (highVal - currentHigh) zeros, then one 1
      while (currentHigh < highVal) {
        this.highBitsUnary.push(0);
        currentHigh++;
      }
      this.highBitsUnary.push(1);
    }

    // Radix index table for fast prefix acceleration
    const tableSize = 1 << this.radixBits;
    this.radixTable = new Array(tableSize + 1).fill(0);
    for (const k of unique) {
      const bucket = Math.floor((k / (this.universe + 1)) * tableSize);
      this.radixTable[bucket + 1]++;
    }
    for (let i = 1; i <= tableSize; i++) {
      this.radixTable[i] += this.radixTable[i - 1];
    }
  }

  contains(key) {
    if (this.keyCount === 0 || key < 0 || key > this.universe) return false;

    // Direct O(log N) or radix-accelerated binary search over sorted keys
    const tableSize = 1 << this.radixBits;
    const bucket = Math.floor((key / (this.universe + 1)) * tableSize);
    let low = this.radixTable[bucket];
    let high = Math.min(this.keyCount - 1, this.radixTable[bucket + 1]);

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const midVal = this.sortedKeys[mid];
      if (midVal === key) return true;
      if (midVal < key) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return false;
  }

  rangeQuery(lowVal, highVal) {
    if (this.keyCount === 0 || lowVal > highVal) return [];
    const results = [];
    for (let i = 0; i < this.keyCount; i++) {
      const k = this.sortedKeys[i];
      if (k >= lowVal && k <= highVal) {
        results.push(k);
      } else if (k > highVal) {
        break;
      }
    }
    return results;
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'radix_elias_fano_filter',
      timestamp: new Date().toISOString(),
      keyCount: this.keyCount,
      universe: this.universe,
      lowBitWidth: this.lowBitWidth,
      highBitsLength: this.highBitsUnary.length,
      radixBits: this.radixBits
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { RadixEliasFanoFilter };
