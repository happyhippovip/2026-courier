const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ShardedLruKCache, LruKCache } = require('../lib/sharded_cache');

// Test 1: LRU-2 evicts one-off scan items before frequently referenced items
const cache = new LruKCache(2, 2); // capacity = 2, k = 2
cache.put('invariant_item', 'System Invariant Token');
cache.get('invariant_item'); // 2nd access -> established in refHistory

cache.put('one_off_1', 'Transient log 1'); // 1 access
// Cache is full (invariant_item, one_off_1). Now insert one_off_2
cache.put('one_off_2', 'Transient log 2');

// LRU-2 must evict one_off_1 (only 1 access) and retain invariant_item (2 accesses)
assert.strictEqual(cache.get('invariant_item'), 'System Invariant Token', 'Invariant item must be retained');
assert.strictEqual(cache.get('one_off_1'), null, 'One-off scan item must be evicted');
console.log('✓ Assertion 1 Passed: LRU-2 correctly protected multi-reference item and evicted transient scan');

// Test 2: Sharded cache distribution
const sharded = new ShardedLruKCache(4, 10, 2);
for (let i = 0; i < 20; i++) {
  sharded.put('key_' + i, 'val_' + i);
}
const stats = sharded.getTotalStats();
assert.strictEqual(stats.totalItems, 20, 'All 20 items must be distributed across shards');
console.log('✓ Assertion 2 Passed: Sharded distribution verified across 4 independent shards');

// Test 3: Hit rate and eviction tracking
sharded.get('key_0');
sharded.get('key_1');
sharded.get('non_existent');
const updatedStats = sharded.getTotalStats();
assert.strictEqual(updatedStats.hits, 2);
assert.strictEqual(updatedStats.misses, 1);
console.log('✓ Assertion 3 Passed: Cache telemetry validated (Hits: 2, Misses: 1)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_SHARDED_LRUK_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  numShards: sharded.numShards,
  stats: updatedStats,
  antiPollutionVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_SHARDED_LRUK_REPORT.json');

console.log('All 4 Sharded LRU-K Cache tests passed successfully!');