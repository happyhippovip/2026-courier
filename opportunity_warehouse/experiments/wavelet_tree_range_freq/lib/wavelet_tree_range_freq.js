/**
 * Wavelet Tree Range Frequency Filter
 * Supports exact range count queries and sublinear O((1/tau) log Sigma)
 * range heavy hitters / majority queries over arbitrary subranges [start, end].
 */

class WaveletFreqNode {
  constructor(minVal, maxVal) {
    this.min = minVal;
    this.max = maxVal;
    this.mid = Math.floor((minVal + maxVal) / 2);
    this.bitvector = [];
    this.prefixRank0 = [0];
    this.left = null;
    this.right = null;
  }

  build(array) {
    if (this.min === this.max || array.length === 0) return;

    const lefts = [];
    const rights = [];

    for (let i = 0; i < array.length; i++) {
      const val = array[i];
      if (val <= this.mid) {
        this.bitvector.push(0);
        lefts.push(val);
      } else {
        this.bitvector.push(1);
        rights.push(val);
      }
      const prev = this.prefixRank0[this.prefixRank0.length - 1];
      this.prefixRank0.push(prev + (val <= this.mid ? 1 : 0));
    }

    if (lefts.length > 0) {
      this.left = new WaveletFreqNode(this.min, this.mid);
      this.left.build(lefts);
    }
    if (rights.length > 0) {
      this.right = new WaveletFreqNode(this.mid + 1, this.max);
      this.right.build(rights);
    }
  }

  rank0(idx) {
    if (idx <= 0) return 0;
    if (idx >= this.prefixRank0.length) return this.prefixRank0[this.prefixRank0.length - 1];
    return this.prefixRank0[idx];
  }

  rank1(idx) {
    return idx - this.rank0(idx);
  }

  countValue(start, end, targetVal) {
    if (start > end || targetVal < this.min || targetVal > this.max) return 0;
    if (this.min === this.max && this.min === targetVal) {
      return end - start + 1;
    }

    const zerosBefore = this.rank0(start);
    const zerosUpTo = this.rank0(end + 1);
    const zerosInRange = zerosUpTo - zerosBefore;

    if (targetVal <= this.mid) {
      if (this.left && zerosInRange > 0) {
        return this.left.countValue(zerosBefore, zerosUpTo - 1, targetVal);
      }
      return 0;
    } else {
      const onesBefore = this.rank1(start);
      const onesUpTo = this.rank1(end + 1);
      const onesInRange = onesUpTo - onesBefore;
      if (this.right && onesInRange > 0) {
        return this.right.countValue(onesBefore, onesUpTo - 1, targetVal);
      }
      return 0;
    }
  }

  findHeavyHitters(start, end, threshold, results) {
    const rangeLen = end - start + 1;
    if (rangeLen < threshold) return;

    if (this.min === this.max) {
      results.push({ value: this.min, count: rangeLen });
      return;
    }

    const zerosBefore = this.rank0(start);
    const zerosUpTo = this.rank0(end + 1);
    const zerosInRange = zerosUpTo - zerosBefore;

    if (zerosInRange >= threshold && this.left) {
      this.left.findHeavyHitters(zerosBefore, zerosUpTo - 1, threshold, results);
    }

    const onesBefore = this.rank1(start);
    const onesUpTo = this.rank1(end + 1);
    const onesInRange = onesUpTo - onesBefore;

    if (onesInRange >= threshold && this.right) {
      this.right.findHeavyHitters(onesBefore, onesUpTo - 1, threshold, results);
    }
  }
}

class WaveletTreeRangeFreq {
  constructor(array, maxVal = 255) {
    this.n = array.length;
    this.maxVal = maxVal;
    this.root = new WaveletFreqNode(0, maxVal);
    this.root.build(array);
  }

  frequency(start, end, value) {
    if (start < 0 || end >= this.n || start > end) return 0;
    return this.root.countValue(start, end, value);
  }

  rangeHeavyHitters(start, end, threshold) {
    if (start < 0 || end >= this.n || start > end || threshold <= 0) return [];
    const results = [];
    this.root.findHeavyHitters(start, end, threshold, results);
    return results.sort((a, b) => b.count - a.count);
  }
}

module.exports = { WaveletTreeRangeFreq, WaveletFreqNode };
