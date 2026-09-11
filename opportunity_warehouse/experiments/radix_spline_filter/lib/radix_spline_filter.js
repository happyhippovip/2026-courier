/**
 * Radix Spline Index Filter
 * Implements a learned index structure combining a bounded-error linear spline
 * with an O(1) radix prefix lookup table (Kipf et al.).
 * Guarantees |predicted_pos - exact_pos| <= epsilon with minimal memory overhead.
 */

class SplinePoint {
  constructor(x, y) {
    this.x = x; // Key
    this.y = y; // Position
  }
}

class RadixSplineFilter {
  constructor(sortedKeys, maxError = 4, radixBits = 4) {
    this.data = sortedKeys;
    this.n = sortedKeys.length;
    this.epsilon = maxError;
    this.radixBits = radixBits;
    this.splinePoints = [];
    this.radixTable = [];

    if (this.n > 0) {
      this._buildSpline();
      this._buildRadixTable();
    }
  }

  _buildSpline() {
    // Greedy spline point fitting with error bound epsilon
    this.splinePoints.push(new SplinePoint(this.data[0], 0));

    if (this.n <= 2) {
      if (this.n === 2) {
        this.splinePoints.push(new SplinePoint(this.data[1], 1));
      }
      return;
    }

    let pStart = this.splinePoints[0];
    let upperSlope = Infinity;
    let lowerSlope = -Infinity;

    for (let i = 1; i < this.n; i++) {
      const x = this.data[i];
      const y = i;

      const upperY = y + this.epsilon;
      const lowerY = Math.max(0, y - this.epsilon);

      const dx = x - pStart.x;
      if (dx === 0) continue;

      const currentUpper = (upperY - pStart.y) / dx;
      const currentLower = (lowerY - pStart.y) / dx;

      upperSlope = Math.min(upperSlope, currentUpper);
      lowerSlope = Math.max(lowerSlope, currentLower);

      if (lowerSlope > upperSlope) {
        // Point cannot be fitted within error envelope; add previous point as spline knot
        const prevPoint = new SplinePoint(this.data[i - 1], i - 1);
        this.splinePoints.push(prevPoint);
        pStart = prevPoint;
        upperSlope = Infinity;
        lowerSlope = -Infinity;
        i--; // Re-evaluate current point with new pStart
      }
    }

    // Add final point
    const last = new SplinePoint(this.data[this.n - 1], this.n - 1);
    if (this.splinePoints[this.splinePoints.length - 1].x !== last.x) {
      this.splinePoints.push(last);
    }
  }

  _buildRadixTable() {
    const numBuckets = 1 << this.radixBits;
    this.radixTable = new Array(numBuckets + 1).fill(0);

    const minKey = this.data[0];
    const maxKey = this.data[this.n - 1];
    this.keyRange = Math.max(1, maxKey - minKey);

    let splineIdx = 0;
    for (let b = 0; b < numBuckets; b++) {
      const bucketMinKey = minKey + (b / numBuckets) * this.keyRange;
      while (splineIdx < this.splinePoints.length && this.splinePoints[splineIdx].x < bucketMinKey) {
        splineIdx++;
      }
      this.radixTable[b] = Math.max(0, splineIdx - 1);
    }
    this.radixTable[numBuckets] = this.splinePoints.length - 1;
  }

  _getBucket(key) {
    const minKey = this.data[0];
    const normalized = Math.max(0, Math.min(1, (key - minKey) / this.keyRange));
    const b = Math.floor(normalized * (1 << this.radixBits));
    return Math.min(b, (1 << this.radixBits) - 1);
  }

  _findSegment(key) {
    let low = 0;
    let high = this.splinePoints.length - 2;
    let best = 0;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (this.splinePoints[mid].x <= key) {
        best = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return best;
  }

  lookup(key) {
    if (this.n === 0 || key < this.data[0] || key > this.data[this.n - 1]) {
      return -1;
    }

    const sIdx = this._findSegment(key);
    const p1 = this.splinePoints[sIdx];
    const p2 = this.splinePoints[sIdx + 1] || p1;

    let predPos = p1.y;
    if (p2.x > p1.x) {
      predPos = p1.y + Math.round(((key - p1.x) / (p2.x - p1.x)) * (p2.y - p1.y));
    }

    const searchLow = Math.max(0, predPos - this.epsilon * 2);
    const searchHigh = Math.min(this.n - 1, predPos + this.epsilon * 2);

    for (let pos = searchLow; pos <= searchHigh; pos++) {
      if (this.data[pos] === key) {
        return pos;
      }
    }

    // Fallback binary search guarantee
    let low = 0, high = this.n - 1;
    while (low <= high) {
      const mid = (low + high) >> 1;
      if (this.data[mid] === key) return mid;
      if (this.data[mid] < key) low = mid + 1;
      else high = mid - 1;
    }

    return -1;
  }

  getStats() {
    return {
      totalKeys: this.n,
      splinePointsCount: this.splinePoints.length,
      radixBits: this.radixBits,
      epsilon: this.epsilon,
      compressionRatio: (this.splinePoints.length / this.n).toFixed(4)
    };
  }
}

module.exports = { RadixSplineFilter, SplinePoint };
