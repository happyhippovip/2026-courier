/**
 * Leveled Hash Filter
 * Implements a two-level hashing structure with bounded worst-case probes (at most 4 buckets).
 * Top level has 2^k buckets; Bottom level has 2^(k-1) buckets.
 * Each bucket contains 4 slots, achieving >85% load factor without cascading displacements.
 */

const crypto = require('crypto');

class LevelBucket {
  constructor(capacity = 4) {
    this.capacity = capacity;
    this.slots = []; // Array of { key, value }
  }

  isFull() {
    return this.slots.length >= this.capacity;
  }

  put(key, value) {
    const idx = this.slots.findIndex(s => s.key === key);
    if (idx !== -1) {
      this.slots[idx].value = value;
      return true;
    }
    if (this.slots.length < this.capacity) {
      this.slots.push({ key, value });
      return true;
    }
    return false;
  }

  get(key) {
    const entry = this.slots.find(s => s.key === key);
    return entry ? entry.value : undefined;
  }

  delete(key) {
    const idx = this.slots.findIndex(s => s.key === key);
    if (idx !== -1) {
      this.slots.splice(idx, 1);
      return true;
    }
    return false;
  }
}

class LeveledHashFilter {
  constructor(k = 4, bucketCapacity = 4) {
    this.k = k;
    this.bucketCapacity = bucketCapacity;
    this.topBucketsCount = 1 << k; // 16 for k=4
    this.bottomBucketsCount = 1 << (k - 1); // 8 for k=4

    this.topLevel = Array.from({ length: this.topBucketsCount }, () => new LevelBucket(bucketCapacity));
    this.bottomLevel = Array.from({ length: this.bottomBucketsCount }, () => new LevelBucket(bucketCapacity));
    this.size = 0;
  }

  _hashes(key) {
    const h = crypto.createHash('sha256').update(String(key)).digest();
    const h1 = h.readUInt32BE(0);
    const h2 = h.readUInt32BE(4);
    return {
      top1: (h1 >>> 0) % this.topBucketsCount,
      top2: (h2 >>> 0) % this.topBucketsCount,
      bot1: (h1 >>> 1) % this.bottomBucketsCount,
      bot2: (h2 >>> 1) % this.bottomBucketsCount
    };
  }

  put(key, value) {
    const { top1, top2, bot1, bot2 } = this._hashes(key);

    // 1. Try Top Level (top1, then top2)
    if (!this.topLevel[top1].isFull()) {
      const isNew = this.topLevel[top1].get(key) === undefined;
      this.topLevel[top1].put(key, value);
      if (isNew) this.size++;
      return true;
    }
    if (!this.topLevel[top2].isFull()) {
      const isNew = this.topLevel[top2].get(key) === undefined;
      this.topLevel[top2].put(key, value);
      if (isNew) this.size++;
      return true;
    }

    // 2. Try Bottom Level (bot1, then bot2)
    if (!this.bottomLevel[bot1].isFull()) {
      const isNew = this.bottomLevel[bot1].get(key) === undefined;
      this.bottomLevel[bot1].put(key, value);
      if (isNew) this.size++;
      return true;
    }
    if (!this.bottomLevel[bot2].isFull()) {
      const isNew = this.bottomLevel[bot2].get(key) === undefined;
      this.bottomLevel[bot2].put(key, value);
      if (isNew) this.size++;
      return true;
    }

    // 3. One-step movement from Top to Bottom
    // Try moving an item from top1 to bottom
    const topB1 = this.topLevel[top1];
    for (let i = 0; i < topB1.slots.length; i++) {
      const candidate = topB1.slots[i];
      const candHashes = this._hashes(candidate.key);
      if (!this.bottomLevel[candHashes.bot1].isFull()) {
        this.bottomLevel[candHashes.bot1].put(candidate.key, candidate.value);
        topB1.slots.splice(i, 1);
        topB1.put(key, value);
        this.size++;
        return true;
      }
    }

    return false; // Table requires resize/rehashing
  }

  get(key) {
    const { top1, top2, bot1, bot2 } = this._hashes(key);
    // At most 4 bucket probes
    let val = this.topLevel[top1].get(key);
    if (val !== undefined) return val;

    val = this.topLevel[top2].get(key);
    if (val !== undefined) return val;

    val = this.bottomLevel[bot1].get(key);
    if (val !== undefined) return val;

    return this.bottomLevel[bot2].get(key);
  }

  has(key) {
    return this.get(key) !== undefined;
  }

  getLoadFactor() {
    const totalSlots = (this.topBucketsCount + this.bottomBucketsCount) * this.bucketCapacity;
    return {
      totalCapacity: totalSlots,
      currentSize: this.size,
      loadFactor: (this.size / totalSlots).toFixed(4)
    };
  }
}

module.exports = { LeveledHashFilter, LevelBucket };
