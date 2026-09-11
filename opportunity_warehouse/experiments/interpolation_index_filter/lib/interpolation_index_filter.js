/**
 * Bounded Interpolation Index Filter
 * Implements a bounded interpolation search index for ordered token sequences.
 * Estimates target positions in O(log log N) time on smooth distributions,
 * with a dynamic step bound that switches to binary search to guarantee O(log N) worst-case.
 */

class BoundedInterpolationIndexFilter {
  constructor(sortedKeys, maxInterpolationSteps = 3) {
    this.data = sortedKeys;
    this.n = sortedKeys.length;
    this.maxSteps = maxInterpolationSteps;
  }

  lookup(key) {
    if (this.n === 0 || key < this.data[0] || key > this.data[this.n - 1]) {
      return -1;
    }

    let low = 0;
    let high = this.n - 1;
    let steps = 0;

    // 1. Bounded interpolation search phase
    while (low <= high && steps < this.maxSteps) {
      if (this.data[low] === key) return low;
      if (this.data[high] === key) return high;
      if (this.data[low] === this.data[high]) break;

      const span = this.data[high] - this.data[low];
      if (span <= 0) break;

      // Linear interpolation formula
      const fraction = (key - this.data[low]) / span;
      let mid = low + Math.floor(fraction * (high - low));

      // Clamp mid to [low, high]
      mid = Math.max(low, Math.min(high, mid));

      if (this.data[mid] === key) {
        return mid;
      }

      if (this.data[mid] < key) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }

      steps++;
    }

    // 2. Guaranteed binary search fallback phase
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
      minKey: this.data[0],
      maxKey: this.data[this.n - 1],
      maxInterpolationSteps: this.maxSteps
    };
  }
}

module.exports = { BoundedInterpolationIndexFilter };
