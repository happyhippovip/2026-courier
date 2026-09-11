const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixRoaringBitVectorIndexer } = require('../lib/radix_roaring_bitvector_indexer');

console.log('Testing Radix Roaring Bit-Vector Indexer...');
const indexer = new RadixRoaringBitVectorIndexer();

// Add sparse items in bucket 0
indexer.add(10);
indexer.add(100);
indexer.add(5000);
assert.ok(indexer.contains(10));
assert.ok(indexer.contains(100));
assert.ok(indexer.contains(5000));
assert.ok(!indexer.contains(999));

// Add items across high bucket boundaries
indexer.add(65536 + 42); // bucket 1
assert.ok(indexer.contains(65536 + 42));
assert.ok(!indexer.contains(65536 + 43));

const stats = indexer.getContainerStats();
assert.strictEqual(stats.totalContainers, 2);
assert.strictEqual(stats.arrayContainers, 2);
assert.strictEqual(stats.bitmapContainers, 0);
assert.strictEqual(stats.totalCardinality, 4);

const report = {
  experiment: 'radix_roaring_bitvector_indexer',
  status: 'VERIFIED',
  testSuite: 'test_radix_roaring_bitvector_indexer',
  stats: stats,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(
  path.join(__dirname, 'SAMPLE_RADIX_ROARING_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);

console.log('✓ Radix Roaring Bit-Vector Indexer verified successfully.');
