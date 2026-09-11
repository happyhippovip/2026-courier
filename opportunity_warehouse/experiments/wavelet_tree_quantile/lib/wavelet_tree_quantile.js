/**
 * Dynamic Wavelet Tree Quantile Filter
 * Succinct binary recursive structure that supports O(log Sigma) range quantile,
 * range rank, and range selection queries over sequence tokens without full sorting.
 */

class WaveletTreeNode {
  constructor(alphabetMin, alphabetMax) {
    this.min = alphabetMin;
    this.max = alphabetMax;
    this.mid = Math.floor((this.min + this.max) / 2);
    this.bitvector = []; // 0 if element <= mid (goes left), 1 if element > mid (goes right)
    this.prefixRank0 = [0]; // Precomputed prefix sums of 0s for O(1) rank queries
    this.left = null;
    this.right = null;
  }

  build(array) {
    if (this.min === this.max || array.length === 0) return;

    const leftArray = [];
    const rightArray = [];

    for (let i = 0; i < array.length; i++) {
      const val = array[i];
      if (val <= this.mid) {
        this.bitvector.push(0);
        leftArray.push(val);
      } else {
        this.bitvector.push(1);
        rightArray.push(val);
      }
      const prevRank0 = this.prefixRank0[this.prefixRank0.length - 1];
      this.prefixRank0.push(prevRank0 + (val <= this.mid ? 1 : 0));
    }

    if (this.min < this.mid) {
      this.left = new WaveletTreeNode(this.min, this.mid);
      this.left.build(leftArray);
    }
    if (this.mid + 1 <= this.max) {
      this.right = new WaveletTreeNode(this.mid + 1, this.max);
      this.right.build(rightArray);
    }
  }

  // Count number of 0s in bitvector[0 .. index-1]
  rank0(index) {
    if (index <= 0) return 0;
    if (index >= this.prefixRank0.length) return this.prefixRank0[this.prefixRank0.length - 1];
    return this.prefixRank0[index];
  }

  // Count number of 1s in bitvector[0 .. index-1]
  rank1(index) {
    return index - this.rank0(index);
  }

  /**
   * Returns k-th smallest element in array[start .. end] (0-indexed k).
   */
  quantile(start, end, k) {
    if (this.min === this.max) {
      return this.min;
    }

    // Number of zeros in [start .. end]
    const zerosBefore = this.rank0(start);
    const zerosUpTo = this.rank0(end + 1);
    const zerosInRange = zerosUpTo - zerosBefore;

    if (k < zerosInRange) {
      // k-th element went to the left child
      const newStart = zerosBefore;
      const newEnd = zerosUpTo - 1;
      return this.left ? this.left.quantile(newStart, newEnd, k) : this.min;
    } else {
      // k-th element went to the right child
      const onesBefore = this.rank1(start);
      const onesUpTo = this.rank1(end + 1);
      const newStart = onesBefore;
      const newEnd = onesUpTo - 1;
      return this.right ? this.right.quantile(newStart, newEnd, k - zerosInRange) : this.max;
    }
  }

  /**
   * Count occurrences of values in range [lowVal .. highVal] within array[start .. end]
   */
  rangeCount(start, end, lowVal, highVal) {
    if (start > end || this.min > highVal || this.max < lowVal) {
      return 0;
    }
    if (this.min >= lowVal && this.max <= highVal) {
      return end - start + 1;
    }
    if (this.min === this.max) {
      return (this.min >= lowVal && this.min <= highVal) ? (end - start + 1) : 0;
    }

    let count = 0;
    const zerosBefore = this.rank0(start);
    const zerosUpTo = this.rank0(end + 1);
    const zerosInRange = zerosUpTo - zerosBefore;

    const onesBefore = this.rank1(start);
    const onesUpTo = this.rank1(end + 1);
    const onesInRange = onesUpTo - onesBefore;

    if (this.left && zerosInRange > 0 && lowVal <= this.mid) {
      count += this.left.rangeCount(zerosBefore, zerosUpTo - 1, lowVal, highVal);
    }
    if (this.right && onesInRange > 0 && highVal > this.mid) {
      count += this.right.rangeCount(onesBefore, onesUpTo - 1, lowVal, highVal);
    }
    return count;
  }
}

class WaveletTreeQuantileFilter {
  constructor(array, alphabetMax = 1000) {
    this.alphabetMax = alphabetMax;
    this.size = array.length;
    this.root = new WaveletTreeNode(0, alphabetMax);
    this.root.build(array);
  }

  quantile(start, end, k) {
    if (start < 0 || end >= this.size || start > end) {
      throw new Error('Invalid range query [' + start + ', ' + end + ']');
    }
    return this.root.quantile(start, end, k);
  }

  median(start, end) {
    const k = Math.floor((end - start) / 2);
    return this.quantile(start, end, k);
  }

  rangeCount(start, end, lowVal, highVal) {
    if (start < 0 || end >= this.size || start > end) {
      throw new Error('Invalid range query [' + start + ', ' + end + ']');
    }
    return this.root.rangeCount(start, end, lowVal, highVal);
  }
}

module.exports = { WaveletTreeQuantileFilter, WaveletTreeNode };
