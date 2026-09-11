/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix Spline Range Filter
 * Implements a RadixSpline learned index: piecewise linear spline approximating
 * CDF with bounded error epsilon, accelerated by radix prefix lookup.
 */

class RadixSplineRangeFilter {
  constructor(maxError = 2) {
    this.maxError = maxError;
    this.keys = [];
    this.splinePoints = []; // array of { key, pos }
    this.radixTable = [];   // radix prefix -> spline segment index
    this.radixShift = 0;
  }

  build(sortedKeys) {
    this.keys = [...sortedKeys];
    const n = this.keys.length;
    if (n === 0) return;

    // 1. Fit greedy linear spline within error bounds
    this.splinePoints = [{ key: this.keys[0], pos: 0 }];
    let currPoint = this.splinePoints[0];

    for (let i = 1; i < n; i++) {
      const k = this.keys[i];
      // Check if line from currPoint to (k, i) keeps all intermediate points within maxError
      let valid = true;
      const slope = (i - currPoint.pos) / Math.max(1, k - currPoint.key);

      for (let j = currPoint.pos + 1; j < i; j++) {
        const estimatedPos = currPoint.pos + slope * (this.keys[j] - currPoint.key);
        if (Math.abs(estimatedPos - j) > this.maxError) {
          valid = false;
          break;
        }
      }

      if (!valid) {
        // Add previous point as spline knot
        const knot = { key: this.keys[i - 1], pos: i - 1 };
        this.splinePoints.push(knot);
        currPoint = knot;
      }
    }

    if (this.splinePoints[this.splinePoints.length - 1].pos !== n - 1) {
      this.splinePoints.push({ key: this.keys[n - 1], pos: n - 1 });
    }

    // 2. Build Radix Table over spline points
    const minKey = this.keys[0];
    const maxKey = this.keys[n - 1];
    const range = Math.max(1, maxKey - minKey);

    const radixBuckets = 16;
    this.radixTable = new Array(radixBuckets).fill(0);

    for (let b = 0; b < radixBuckets; b++) {
      const bucketKey = minKey + (b / radixBuckets) * range;
      // find first spline point >= bucketKey
      let spIdx = 0;
      while (spIdx < this.splinePoints.length - 1 && this.splinePoints[spIdx + 1].key <= bucketKey) {
        spIdx++;
      }
      this.radixTable[b] = spIdx;
    }
  }

  _estimatePos(key) {
    if (this.keys.length === 0) return -1;
    if (key <= this.keys[0]) return 0;
    if (key >= this.keys[this.keys.length - 1]) return this.keys.length - 1;

    // Radix lookup to find spline point
    const minKey = this.keys[0];
    const maxKey = this.keys[this.keys.length - 1];
    const range = Math.max(1, maxKey - minKey);
    const bucket = Math.min(15, Math.max(0, Math.floor(((key - minKey) / range) * 16)));
    let spIdx = this.radixTable[bucket];

    while (spIdx < this.splinePoints.length - 1 && this.splinePoints[spIdx + 1].key < key) {
      spIdx++;
    }

    const p1 = this.splinePoints[spIdx];
    const p2 = this.splinePoints[spIdx + 1] || p1;
    if (p1.key === p2.key) return p1.pos;

    const slope = (p2.pos - p1.pos) / (p2.key - p1.key);
    return Math.round(p1.pos + slope * (key - p1.key));
  }

  search(key) {
    const est = this._estimatePos(key);
    if (est === -1) return null;

    const low = Math.max(0, est - this.maxError * 2);
    const high = Math.min(this.keys.length - 1, est + this.maxError * 2);

    for (let i = low; i <= high; i++) {
      if (this.keys[i] === key) return i;
    }
    return null;
  }

  rangeQuery(lowKey, highKey) {
    const estLow = this._estimatePos(lowKey);
    const estHigh = this._estimatePos(highKey);

    const start = Math.max(0, estLow - this.maxError * 2);
    const end = Math.min(this.keys.length - 1, estHigh + this.maxError * 2);

    const results = [];
    for (let i = start; i <= end; i++) {
      if (this.keys[i] >= lowKey && this.keys[i] <= highKey) {
        results.push(this.keys[i]);
      }
    }
    return results;
  }

  getMetrics() {
    return {
      keyCount: this.keys.length,
      splinePointCount: this.splinePoints.length,
      maxError: this.maxError,
      compressionFactor: Number((this.splinePoints.length / Math.max(1, this.keys.length)).toFixed(4))
    };
  }
}

module.exports = { RadixSplineRangeFilter };
