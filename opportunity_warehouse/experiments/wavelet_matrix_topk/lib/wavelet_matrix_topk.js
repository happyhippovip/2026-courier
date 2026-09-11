/**
 * Wavelet Matrix Top-K Heavy Saliency Filter
 * Efficiently discovers the Top-K highest saliency tokens in any subrange [start, end]
 * in O(K log Sigma) time using priority branch traversal over succinct bitvectors.
 */

class SuccinctBitVector {
  constructor(bits) {
    this.bits = bits;
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

class WaveletMatrixTopK {
  constructor(array, maxVal = 255) {
    this.n = array.length;
    this.maxVal = maxVal;
    this.levels = Math.max(1, Math.ceil(Math.log2(maxVal + 1)));
    this.bitvectors = [];
    this.zerosCount = [];

    let currentArray = array.slice();

    for (let l = this.levels - 1; l >= 0; l--) {
      const bits = [];
      const lefts = [];
      const rights = [];

      for (let i = 0; i < currentArray.length; i++) {
        const val = currentArray[i];
        const bit = (val >> l) & 1;
        bits.push(bit);
        if (bit === 0) lefts.push(val);
        else rights.push(val);
      }

      const bv = new SuccinctBitVector(bits);
      this.bitvectors.push(bv);
      this.zerosCount.push(bv.totalZeros);
      currentArray = lefts.concat(rights);
    }
  }

  /**
   * Discovers the top-K highest values in array[start .. end] with their exact frequencies.
   */
  getTopK(start, end, k) {
    if (start < 0 || end >= this.n || start > end || k <= 0) {
      return [];
    }

    const results = [];
    let itemsFound = 0;

    // Priority Queue item: { level, start, end, prefixVal, maxPotentialVal }
    // Max potential value is prefixVal + (2^(levels - level) - 1)
    const pq = [];

    const insertPQ = (item) => {
      pq.push(item);
      pq.sort((a, b) => b.maxPotentialVal - a.maxPotentialVal);
    };

    const initialMaxPotential = (1 << this.levels) - 1;
    insertPQ({
      level: 0,
      start,
      end,
      prefixVal: 0,
      maxPotentialVal: initialMaxPotential
    });

    while (pq.length > 0 && results.length < k) {
      const node = pq.shift();

      if (node.level === this.levels) {
        // Reached leaf: node.prefixVal is the exact value, frequency is (node.end - node.start + 1)
        const count = node.end - node.start + 1;
        results.push({ value: node.prefixVal, count });
        if (results.length >= k) break;
        continue;
      }

      const l = node.level;
      const bitWeight = 1 << (this.levels - 1 - l);
      const bv = this.bitvectors[l];
      const z = this.zerosCount[l];

      const zerosBefore = bv.rank0(node.start);
      const zerosUpTo = bv.rank0(node.end + 1);
      const zerosInRange = zerosUpTo - zerosBefore;

      const onesBefore = bv.rank1(node.start);
      const onesUpTo = bv.rank1(node.end + 1);
      const onesInRange = onesUpTo - onesBefore;

      // Explore 1-branch (higher value)
      if (onesInRange > 0) {
        const nextStart = z + onesBefore;
        const nextEnd = z + onesUpTo - 1;
        const nextPrefix = node.prefixVal | bitWeight;
        const remainingBits = (1 << (this.levels - 1 - l)) - 1;
        insertPQ({
          level: l + 1,
          start: nextStart,
          end: nextEnd,
          prefixVal: nextPrefix,
          maxPotentialVal: nextPrefix + remainingBits
        });
      }

      // Explore 0-branch (lower value)
      if (zerosInRange > 0) {
        const nextStart = zerosBefore;
        const nextEnd = zerosUpTo - 1;
        const nextPrefix = node.prefixVal;
        const remainingBits = (1 << (this.levels - 1 - l)) - 1;
        insertPQ({
          level: l + 1,
          start: nextStart,
          end: nextEnd,
          prefixVal: nextPrefix,
          maxPotentialVal: nextPrefix + remainingBits
        });
      }
    }

    return results.slice(0, k);
  }
}

module.exports = { WaveletMatrixTopK, SuccinctBitVector };
