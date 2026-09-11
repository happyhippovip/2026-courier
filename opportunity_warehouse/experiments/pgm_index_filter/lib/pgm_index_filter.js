/**
 * Piecewise Geometric Model (PGM) Index Filter
 * Implements a learned index that models the cumulative distribution of sorted token keys
 * using a piecewise linear approximation with provable error bound epsilon (Ferragina & Vinciguerra).
 */

class PGMSegment {
  constructor(key, slope, intercept) {
    this.key = key; // First key in segment
    this.slope = slope;
    this.intercept = intercept;
  }

  predict(x) {
    return Math.round(this.slope * x + this.intercept);
  }
}

class PGMIndexFilter {
  constructor(sortedKeys, epsilon = 4) {
    this.data = sortedKeys;
    this.n = sortedKeys.length;
    this.epsilon = epsilon;
    this.segments = [];

    if (this.n > 0) {
      this._build();
    }
  }

  _build() {
    let startIdx = 0;

    while (startIdx < this.n) {
      const firstKey = this.data[startIdx];
      let endIdx = startIdx;
      let minSlope = -Infinity;
      let maxSlope = Infinity;

      // Expand segment as long as points fall within epsilon corridor
      for (let i = startIdx + 1; i < this.n; i++) {
        const dx = this.data[i] - firstKey;
        if (dx === 0) continue;

        const dy = i - startIdx;
        const currentMin = (dy - this.epsilon) / dx;
        const currentMax = (dy + this.epsilon) / dx;

        const newMin = Math.max(minSlope, currentMin);
        const newMax = Math.min(maxSlope, currentMax);

        if (newMin > newMax) {
          // Corridor closed; segment ends at i - 1
          break;
        }

        minSlope = newMin;
        maxSlope = newMax;
        endIdx = i;
      }

      const slope = minSlope === -Infinity ? 0 : (minSlope + maxSlope) / 2;
      const intercept = startIdx - slope * firstKey;
      this.segments.push(new PGMSegment(firstKey, slope, intercept));

      startIdx = endIdx + 1;
    }
  }

  _findSegment(key) {
    let low = 0;
    let high = this.segments.length - 1;
    let best = 0;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (this.segments[mid].key <= key) {
        best = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return this.segments[best];
  }

  lookup(key) {
    if (this.n === 0 || key < this.data[0] || key > this.data[this.n - 1]) {
      return -1;
    }

    const seg = this._findSegment(key);
    const predictedPos = seg.predict(key);

    const searchLow = Math.max(0, predictedPos - this.epsilon * 2);
    const searchHigh = Math.min(this.n - 1, predictedPos + this.epsilon * 2);

    for (let pos = searchLow; pos <= searchHigh; pos++) {
      if (this.data[pos] === key) {
        return pos;
      }
    }

    // Binary search fallback guarantee
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
      segmentCount: this.segments.length,
      epsilon: this.epsilon,
      compressionRatio: (this.segments.length / this.n).toFixed(4)
    };
  }
}

module.exports = { PGMIndexFilter, PGMSegment };
