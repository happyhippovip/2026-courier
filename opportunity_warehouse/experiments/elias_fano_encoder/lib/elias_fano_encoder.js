/**
 * Context Window Token Dynamic Bounded Fast Succinct Elias-Fano Monotonic Encoder
 * Encodes sorted, non-decreasing integer sequences (e.g., token offsets, sorted document IDs)
 * with near-optimal information theoretic compression and O(1) random access.
 */

class EliasFanoEncoder {
  constructor() {
    this.n = 0;
    this.U = 0;
    this.l = 0;
    this.lowBits = [];
    this.highBits = [];
    this.select1Table = [];
  }

  encode(sortedArray) {
    if (!Array.isArray(sortedArray) || sortedArray.length === 0) {
      throw new Error('Input must be a non-empty array of sorted integers');
    }

    this.n = sortedArray.length;
    this.U = sortedArray[this.n - 1] + 1;
    this.l = Math.max(0, Math.floor(Math.log2(this.U / this.n)));

    this.lowBits = [];
    this.highBits = [];
    this.select1Table = [];

    const lowMask = (1 << this.l) - 1;
    let currHigh = 0;

    for (let i = 0; i < this.n; i++) {
      const val = sortedArray[i];
      if (i > 0 && val < sortedArray[i - 1]) {
        throw new Error('Array elements must be in non-decreasing order');
      }

      this.lowBits.push(val & lowMask);
      const h = val >>> this.l;

      while (currHigh < h) {
        this.highBits.push(0);
        currHigh++;
      }
      this.highBits.push(1);
    }

    // Build select1 table for O(1) random access
    for (let idx = 0; idx < this.highBits.length; idx++) {
      if (this.highBits[idx] === 1) {
        this.select1Table.push(idx);
      }
    }

    return this.getMetrics();
  }

  get(index) {
    if (index < 0 || index >= this.n) return null;
    const highPos = this.select1Table[index];
    const h = highPos - index;
    return (h << this.l) | this.lowBits[index];
  }

  predecessor(target) {
    // Binary search over index range [0, n - 1] to find largest value <= target
    let low = 0;
    let high = this.n - 1;
    let bestIdx = -1;

    while (low <= high) {
      const mid = (low + high) >>> 1;
      const midVal = this.get(mid);
      if (midVal <= target) {
        bestIdx = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    if (bestIdx === -1) return null;
    return { index: bestIdx, value: this.get(bestIdx) };
  }

  toArray() {
    const result = [];
    for (let i = 0; i < this.n; i++) {
      result.push(this.get(i));
    }
    return result;
  }

  getMetrics() {
    const lowBitsTotal = this.n * this.l;
    const highBitsTotal = this.highBits.length;
    const totalBits = lowBitsTotal + highBitsTotal;
    const compressedBytes = Math.ceil(totalBits / 8);
    const rawBytes = this.n * 4; // 32-bit int representation
    const compressionRatio = rawBytes > 0 
      ? (1 - (compressedBytes / rawBytes)).toFixed(4)
      : '0.0000';

    return {
      elementCount: this.n,
      universeBound: this.U,
      lowerBitWidth: this.l,
      totalBits,
      compressedBytes,
      rawBytes,
      compressionRatio: parseFloat(compressionRatio),
      savingsPercent: (parseFloat(compressionRatio) * 100).toFixed(2) + '%'
    };
  }
}

module.exports = { EliasFanoEncoder };
