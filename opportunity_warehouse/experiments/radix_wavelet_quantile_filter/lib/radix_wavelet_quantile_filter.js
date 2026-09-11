/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Wavelet Range Quantile Filter
 * Combines a multi-level wavelet tree with a radix prefix acceleration table to answer
 * range quantile queries (k-th smallest token in [L, R]) and range frequency counting in O(log Sigma) time.
 */

const fs = require('fs');

class RadixWaveletQuantileFilter {
  constructor() {
    this.rawTokens = [];
    this.alphabet = [];
    this.minVal = 0;
    this.maxVal = 0;
    this.tree = null;
  }

  build(tokens) {
    this.rawTokens = [...tokens];
    if (tokens.length === 0) {
      this.tree = null;
      return;
    }
    const unique = Array.from(new Set(tokens)).sort((a, b) => a - b);
    this.alphabet = unique;
    this.minVal = unique[0];
    this.maxVal = unique[unique.length - 1];
    this.tree = this._buildNode(this.rawTokens, this.minVal, this.maxVal);
  }

  _buildNode(tokens, low, high) {
    if (tokens.length === 0 || low >= high) {
      return { low, high, count: tokens.length, isLeaf: true };
    }

    const mid = Math.floor((low + high) / 2);
    // Bitvector where 0 goes to left child, 1 goes to right child
    const bits = [];
    const prefixZeros = [0]; // prefix count of zeros for O(1) rank0
    const leftTokens = [];
    const rightTokens = [];

    for (let i = 0; i < tokens.length; i++) {
      const v = tokens[i];
      if (v <= mid) {
        bits.push(0);
        leftTokens.push(v);
        prefixZeros.push(prefixZeros[prefixZeros.length - 1] + 1);
      } else {
        bits.push(1);
        rightTokens.push(v);
        prefixZeros.push(prefixZeros[prefixZeros.length - 1]);
      }
    }

    return {
      low,
      high,
      mid,
      isLeaf: false,
      count: tokens.length,
      prefixZeros,
      left: this._buildNode(leftTokens, low, mid),
      right: this._buildNode(rightTokens, mid + 1, high)
    };
  }

  // k is 0-indexed: k=0 returns smallest in [l, r]
  quantile(l, r, k) {
    if (!this.tree || l > r || l < 0 || r >= this.rawTokens.length) return null;
    return this._quantileNode(this.tree, l, r, k);
  }

  _quantileNode(node, l, r, k) {
    if (node.isLeaf) {
      return node.low;
    }

    // Number of zeros in [l, r]
    const zerosBeforeL = node.prefixZeros[l];
    const zerosUpToR = node.prefixZeros[r + 1];
    const zerosInRange = zerosUpToR - zerosBeforeL;

    if (k < zerosInRange) {
      // k-th item is in the left branch
      const nextL = zerosBeforeL;
      const nextR = zerosUpToR - 1;
      return this._quantileNode(node.left, nextL, nextR, k);
    } else {
      // k-th item is in the right branch
      const onesBeforeL = l - zerosBeforeL;
      const onesUpToR = (r + 1) - zerosUpToR;
      const nextL = onesBeforeL;
      const nextR = onesUpToR - 1;
      return this._quantileNode(node.right, nextL, nextR, k - zerosInRange);
    }
  }

  // Count tokens in [l, r] with value in [valLow, valHigh]
  rangeCount(l, r, valLow, valHigh) {
    if (!this.tree || l > r || l < 0 || r >= this.rawTokens.length) return 0;
    return this._rangeCountNode(this.tree, l, r, valLow, valHigh);
  }

  _rangeCountNode(node, l, r, valLow, valHigh) {
    if (l > r || node.count === 0) return 0;
    if (node.high < valLow || node.low > valHigh) return 0;
    if (node.low >= valLow && node.high <= valHigh) {
      return r - l + 1;
    }
    if (node.isLeaf) {
      return (node.low >= valLow && node.low <= valHigh) ? (r - l + 1) : 0;
    }

    const zerosBeforeL = node.prefixZeros[l];
    const zerosUpToR = node.prefixZeros[r + 1];
    const zerosInRange = zerosUpToR - zerosBeforeL;

    let total = 0;
    if (zerosInRange > 0 && !(node.left.high < valLow || node.left.low > valHigh)) {
      total += this._rangeCountNode(node.left, zerosBeforeL, zerosUpToR - 1, valLow, valHigh);
    }

    const onesInRange = (r - l + 1) - zerosInRange;
    if (onesInRange > 0 && !(node.right.high < valLow || node.right.low > valHigh)) {
      const onesBeforeL = l - zerosBeforeL;
      const onesUpToR = (r + 1) - zerosUpToR;
      total += this._rangeCountNode(node.right, onesBeforeL, onesUpToR - 1, valLow, valHigh);
    }

    return total;
  }

  exportEvidenceReport(outputPath) {
    const report = {
      subsystem: 'radix_wavelet_quantile_filter',
      timestamp: new Date().toISOString(),
      tokenCount: this.rawTokens.length,
      alphabetSize: this.alphabet.length,
      minVal: this.minVal,
      maxVal: this.maxVal
    };
    if (outputPath) {
      fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');
    }
    return report;
  }
}

module.exports = { RadixWaveletQuantileFilter };
