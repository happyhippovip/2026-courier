/**
 * Context Window Token Dynamic Bounded Fast Succinct Radix-Heap Priority Filter
 * Implements a monotonic Radix Heap with bucketed bit-length partitioning,
 * providing O(1) amortized insert and extract-min for non-decreasing priority sequences.
 */

class RadixHeapFilter {
  constructor(bitWidth = 32) {
    this.bitWidth = bitWidth;
    this.buckets = [];
    this.u = []; // lower bounds of buckets
    for (let i = 0; i <= bitWidth; i++) {
      this.buckets.push([]);
      this.u.push(0);
    }
    this.lastExtracted = 0;
    this.size = 0;
  }

  _getBucketIndex(key) {
    const diff = key ^ this.lastExtracted;
    if (diff === 0) return 0;
    return 32 - Math.clz32(diff);
  }

  insert(key, value) {
    if (key < this.lastExtracted) {
      throw new Error('Monotonicity violation: key ' + key + ' < lastExtracted ' + this.lastExtracted);
    }
    const idx = this._getBucketIndex(key);
    this.buckets[idx].push({ key, value });
    this.size++;
  }

  extractMin() {
    if (this.size === 0) return null;

    if (this.buckets[0].length > 0) {
      this.size--;
      const item = this.buckets[0].pop();
      this.lastExtracted = item.key;
      return item;
    }

    // Find non-empty bucket
    let i = 1;
    while (i <= this.bitWidth && this.buckets[i].length === 0) {
      i++;
    }

    if (i > this.bitWidth) return null;

    // Find min in bucket i
    let minIdx = 0;
    let minKey = this.buckets[i][0].key;
    for (let j = 1; j < this.buckets[i].length; j++) {
      if (this.buckets[i][j].key < minKey) {
        minKey = this.buckets[i][j].key;
        minIdx = j;
      }
    }

    this.lastExtracted = minKey;
    const items = this.buckets[i];
    this.buckets[i] = [];

    // Re-bucket all items in bucket i
    for (let j = 0; j < items.length; j++) {
      const it = items[j];
      const newIdx = this._getBucketIndex(it.key);
      this.buckets[newIdx].push(it);
    }

    // Now bucket 0 is guaranteed to have at least one element with minKey
    this.size--;
    return this.buckets[0].pop();
  }

  isEmpty() {
    return this.size === 0;
  }

  getMetrics() {
    let activeBuckets = 0;
    for (const b of this.buckets) if (b.length > 0) activeBuckets++;
    return {
      size: this.size,
      bitWidth: this.bitWidth,
      lastExtracted: this.lastExtracted,
      activeBuckets,
      complexity: 'O(1)_AMORTIZED_INSERT_EXTRACT',
      queueClass: 'MONOTONIC_RADIX_HEAP'
    };
  }
}

module.exports = { RadixHeapFilter };
