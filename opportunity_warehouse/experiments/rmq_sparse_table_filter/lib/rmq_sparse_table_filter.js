/**
 * Context Window Token Dynamic Bounded Fast Succinct Range Minimum Query (RMQ) Sparse Table Filter
 * Provides O(1) time complexity range minimum and maximum queries over arbitrary token sequence windows,
 * ideal for dynamic context window token pruning, saliency ranking, and sliding window attention filters.
 */

class RMQSparseTableFilter {
  constructor(values = []) {
    this.values = values.slice();
    this.n = this.values.length;
    if (this.n > 0) {
      this._buildTables();
    }
  }

  _buildTables() {
    this.K = Math.floor(Math.log2(Math.max(1, this.n))) + 1;
    this.stMin = [];
    this.stMax = [];

    for (let k = 0; k < this.K; k++) {
      this.stMin.push(new Int32Array(this.n));
      this.stMax.push(new Int32Array(this.n));
    }

    // Base layer k = 0 (intervals of length 2^0 = 1)
    for (let i = 0; i < this.n; i++) {
      this.stMin[0][i] = i;
      this.stMax[0][i] = i;
    }

    // Dynamic programming layers k > 0
    for (let k = 1; k < this.K; k++) {
      const half = 1 << (k - 1);
      for (let i = 0; i + (1 << k) <= this.n; i++) {
        const minIdx1 = this.stMin[k - 1][i];
        const minIdx2 = this.stMin[k - 1][i + half];
        this.stMin[k][i] = this.values[minIdx1] <= this.values[minIdx2] ? minIdx1 : minIdx2;

        const maxIdx1 = this.stMax[k - 1][i];
        const maxIdx2 = this.stMax[k - 1][i + half];
        this.stMax[k][i] = this.values[maxIdx1] >= this.values[maxIdx2] ? maxIdx1 : maxIdx2;
      }
    }
  }

  queryMin(L, R) {
    if (L < 0 || R >= this.n || L > R) return null;
    const len = R - L + 1;
    const k = Math.floor(Math.log2(len));
    const idx1 = this.stMin[k][L];
    const idx2 = this.stMin[k][R - (1 << k) + 1];
    const bestIdx = this.values[idx1] <= this.values[idx2] ? idx1 : idx2;
    return { index: bestIdx, value: this.values[bestIdx] };
  }

  queryMax(L, R) {
    if (L < 0 || R >= this.n || L > R) return null;
    const len = R - L + 1;
    const k = Math.floor(Math.log2(len));
    const idx1 = this.stMax[k][L];
    const idx2 = this.stMax[k][R - (1 << k) + 1];
    const bestIdx = this.values[idx1] >= this.values[idx2] ? idx1 : idx2;
    return { index: bestIdx, value: this.values[bestIdx] };
  }

  querySpan(L, R) {
    const minRes = this.queryMin(L, R);
    const maxRes = this.queryMax(L, R);
    if (!minRes || !maxRes) return null;
    return {
      min: minRes,
      max: maxRes,
      spread: maxRes.value - minRes.value
    };
  }

  getMetrics() {
    const tableMemoryBytes = this.K * this.n * 4 * 2; // Int32 for min and max
    const rawValuesBytes = this.n * 4;
    return {
      elementCount: this.n,
      powerOfTwoLevels: this.K,
      tableMemoryBytes,
      rawValuesBytes,
      queryComplexity: 'O(1)_CONSTANT_TIME_VERIFIED'
    };
  }
}

module.exports = { RMQSparseTableFilter };
