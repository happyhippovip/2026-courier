/**
 * Succinct Wavelet Matrix Quantile Evaluator
 * Implements Claude & Navarro's pointerless Wavelet Matrix structure.
 * Stores sequence over alphabet [0..Sigma-1] using only L = ceil(log2 Sigma)
 * bitvectors of length n, supporting O(L) range quantile selection and rank queries.
 */

class SuccinctBitVector {
  constructor(bits) {
    this.bits = bits; // Array of 0s and 1s
    this.length = bits.length;
    this.prefixRank0 = [0];
    let count0 = 0;
    for (let i = 0; i < bits.length; i++) {
      if (bits[i] === 0) count0++;
      this.prefixRank0.push(count0);
    }
    this.totalZeros = count0;
  }

  rank0(idx) {
    if (idx <= 0) return 0;
    if (idx >= this.prefixRank0.length) return this.totalZeros;
    return this.prefixRank0[idx];
  }

  rank1(idx) {
    if (idx <= 0) return 0;
    if (idx > this.length) idx = this.length;
    return idx - this.rank0(idx);
  }
}

class WaveletMatrixQuantile {
  constructor(array, maxVal = 255) {
    this.n = array.length;
    this.maxVal = maxVal;
    // Number of bits needed
    this.levels = Math.max(1, Math.ceil(Math.log2(maxVal + 1)));
    this.bitvectors = [];
    this.zerosCount = [];

    let currentArray = array.slice();

    // Build levels from MSB down to LSB
    for (let l = this.levels - 1; l >= 0; l--) {
      const bits = [];
      const lefts = [];
      const rights = [];

      for (let i = 0; i < currentArray.length; i++) {
        const val = currentArray[i];
        const bit = (val >> l) & 1;
        bits.push(bit);
        if (bit === 0) {
          lefts.push(val);
        } else {
          rights.push(val);
        }
      }

      const bv = new SuccinctBitVector(bits);
      this.bitvectors.push(bv);
      this.zerosCount.push(bv.totalZeros);

      // Concatenate lefts then rights for next level
      currentArray = lefts.concat(rights);
    }
  }

  /**
   * Quantile query: returns k-th smallest element in range [start, end] (0-indexed k).
   */
  quantile(start, end, k) {
    if (start < 0 || end >= this.n || start > end || k < 0 || k > (end - start)) {
      throw new Error('Invalid quantile query parameters: [' + start + ', ' + end + '], k=' + k);
    }

    let curStart = start;
    let curEnd = end;
    let result = 0;

    for (let l = 0; l < this.levels; l++) {
      const bitWeight = 1 << (this.levels - 1 - l);
      const bv = this.bitvectors[l];
      const z = this.zerosCount[l];

      const zerosBefore = bv.rank0(curStart);
      const zerosUpTo = bv.rank0(curEnd + 1);
      const zerosInRange = zerosUpTo - zerosBefore;

      if (k < zerosInRange) {
        // Value has bit 0 at this position
        curStart = zerosBefore;
        curEnd = zerosUpTo - 1;
      } else {
        // Value has bit 1 at this position
        result |= bitWeight;
        k -= zerosInRange;
        const onesBefore = bv.rank1(curStart);
        const onesUpTo = bv.rank1(curEnd + 1);
        curStart = z + onesBefore;
        curEnd = z + onesUpTo - 1;
      }
    }

    return result;
  }

  median(start, end) {
    const k = Math.floor((end - start) / 2);
    return this.quantile(start, end, k);
  }

  getCompressionStats() {
    return {
      sequenceLength: this.n,
      bitLevels: this.levels,
      totalBits: this.n * this.levels,
      rawInt32Bits: this.n * 32,
      compressionRatio: ((this.n * this.levels) / (this.n * 32)).toFixed(4)
    };
  }
}

module.exports = { WaveletMatrixQuantile, SuccinctBitVector };
