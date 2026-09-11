/**
 * Context Window Token Stream-Summary Heavy Hitters Evaluator
 * True O(1) Space-Saving algorithm utilizing the Stream-Summary data structure.
 * Bucket list of counts linked with doubly linked list of items per bucket.
 * Insertion, promotion, and minimum eviction execute strictly in O(1) time.
 */

class ItemNode {
  constructor(key, bucket) {
    this.key = key;
    this.bucket = bucket;
    this.prev = null;
    this.next = null;
    this.error = 0;
  }
}

class BucketNode {
  constructor(count) {
    this.count = count;
    this.headItem = null;
    this.prevBucket = null;
    this.nextBucket = null;
  }

  addItem(item) {
    item.bucket = this;
    item.prev = null;
    item.next = this.headItem;
    if (this.headItem) {
      this.headItem.prev = item;
    }
    this.headItem = item;
  }

  removeItem(item) {
    if (item.prev) item.prev.next = item.next;
    if (item.next) item.next.prev = item.prev;
    if (this.headItem === item) {
      this.headItem = item.next;
    }
    item.prev = null;
    item.next = null;
  }

  isEmpty() {
    return this.headItem === null;
  }
}

class StreamSummary {
  constructor(k = 64) {
    this.k = k;
    this.itemMap = new Map(); // key -> ItemNode
    this.headBucket = null; // Bucket with minimum count
    this.totalEvents = 0;
  }

  _removeBucket(b) {
    if (b.prevBucket) b.prevBucket.nextBucket = b.nextBucket;
    if (b.nextBucket) b.nextBucket.prevBucket = b.prevBucket;
    if (this.headBucket === b) {
      this.headBucket = b.nextBucket;
    }
  }

  _incrementItem(item) {
    const oldBucket = item.bucket;
    const newCount = oldBucket.count + 1;
    oldBucket.removeItem(item);

    // Find or create bucket for newCount
    let nextB = oldBucket.nextBucket;
    if (!nextB || nextB.count !== newCount) {
      const newB = new BucketNode(newCount);
      newB.prevBucket = oldBucket;
      newB.nextBucket = nextB;
      if (nextB) nextB.prevBucket = newB;
      oldBucket.nextBucket = newB;
      nextB = newB;
    }

    nextB.addItem(item);

    if (oldBucket.isEmpty()) {
      this._removeBucket(oldBucket);
    }
  }

  add(key) {
    this.totalEvents++;

    if (this.itemMap.has(key)) {
      this._incrementItem(this.itemMap.get(key));
      return;
    }

    if (this.itemMap.size < this.k) {
      // Create bucket 1 if not exists
      if (!this.headBucket || this.headBucket.count !== 1) {
        const b1 = new BucketNode(1);
        b1.nextBucket = this.headBucket;
        if (this.headBucket) this.headBucket.prevBucket = b1;
        this.headBucket = b1;
      }
      const item = new ItemNode(key, this.headBucket);
      this.headBucket.addItem(item);
      this.itemMap.set(key, item);
      return;
    }

    // Evict minimum element in O(1)
    const minBucket = this.headBucket;
    const evictItem = minBucket.headItem;
    this.itemMap.delete(evictItem.key);

    const newError = minBucket.count;
    evictItem.key = key;
    evictItem.error = newError;
    this.itemMap.set(key, evictItem);

    this._incrementItem(evictItem);
  }

  getEstimate(key) {
    const item = this.itemMap.get(key);
    if (!item) return { count: 0, error: 0 };
    return { count: item.bucket.count, error: item.error };
  }

  getHeavyHitters() {
    const list = [];
    for (const item of this.itemMap.values()) {
      list.push({
        key: item.key,
        count: item.bucket.count,
        error: item.error,
        guaranteedCount: item.bucket.count - item.error
      });
    }
    return list.sort((a, b) => b.count - a.count);
  }
}

module.exports = { StreamSummary };
