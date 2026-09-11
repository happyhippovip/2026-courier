/**
 * Context Window Sharded LRU-K Cache & Eviction Controller
 * Implements an LRU-2 (K=2) cache tracking the second-to-last reference timestamp of items,
 * eliminating cache pollution from one-off scans and protecting high-frequency invariant context.
 */

class LruKCache {
  constructor(capacity = 50, k = 2) {
    this.capacity = capacity;
    this.k = k;
    this.items = new Map(); // key -> { value, refHistory: [] }
    this.hits = 0;
    this.misses = 0;
    this.evictions = 0;
  }

  get(key) {
    const record = this.items.get(key);
    if (!record) {
      this.misses += 1;
      return null;
    }
    this.hits += 1;
    record.refHistory.push(Date.now());
    if (record.refHistory.length > this.k) {
      record.refHistory.shift();
    }
    return record.value;
  }

  getKDistance(record, now) {
    if (record.refHistory.length < this.k) {
      return Infinity; // High priority for eviction if accessed fewer than K times
    }
    // Backward distance: now - time of k-th previous reference
    return now - record.refHistory[0];
  }

  evictOne() {
    const now = Date.now();
    let victimKey = null;
    let maxDistance = -1;

    for (const [key, record] of this.items.entries()) {
      const dist = this.getKDistance(record, now);
      if (dist > maxDistance) {
        maxDistance = dist;
        victimKey = key;
      }
    }

    if (victimKey !== null) {
      this.items.delete(victimKey);
      this.evictions += 1;
    }
    return victimKey;
  }

  put(key, value) {
    if (this.items.has(key)) {
      const record = this.items.get(key);
      record.value = value;
      record.refHistory.push(Date.now());
      if (record.refHistory.length > this.k) record.refHistory.shift();
      return;
    }

    if (this.items.size >= this.capacity) {
      this.evictOne();
    }

    this.items.set(key, {
      value,
      refHistory: [Date.now()]
    });
  }
}

class ShardedLruKCache {
  constructor(numShards = 4, shardCapacity = 25, k = 2) {
    this.numShards = numShards;
    this.shards = Array.from({ length: numShards }, () => new LruKCache(shardCapacity, k));
  }

  getShardIndex(key) {
    let hash = 0;
    for (let i = 0; i < key.length; i++) {
      hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
    }
    return hash % this.numShards;
  }

  get(key) {
    return this.shards[this.getShardIndex(key)].get(key);
  }

  put(key, value) {
    this.shards[this.getShardIndex(key)].put(key, value);
  }

  getTotalStats() {
    return this.shards.reduce((acc, shard) => ({
      hits: acc.hits + shard.hits,
      misses: acc.misses + shard.misses,
      evictions: acc.evictions + shard.evictions,
      totalItems: acc.totalItems + shard.items.size
    }), { hits: 0, misses: 0, evictions: 0, totalItems: 0 });
  }
}

module.exports = { ShardedLruKCache, LruKCache };