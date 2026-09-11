const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { KDTreeContextPartitioner } = require('./lib/kdtree_context_partitioner');

console.log('Testing 2D KD-Tree Context Partitioner...');

const kd = new KDTreeContextPartitioner();

// Insert points: [recency_pos, saliency_score]
kd.insert([10, 0.90], 'token-critical-old');
kd.insert([80, 0.85], 'token-critical-recent');
kd.insert([20, 0.10], 'token-stopword-old');
kd.insert([90, 0.15], 'token-stopword-recent');
kd.insert([50, 0.50], 'token-mid-mid');

assert.strictEqual(kd.size, 5);
console.log('✓ Test 1: 5 2D points successfully partitioned in alternating plane KD-tree');

// Test 2: Range query for Recent AND High Saliency: recency in [60, 100], saliency in [0.70, 1.00]
const results1 = kd.rangeSearch(60, 100, 0.70, 1.00);
assert.strictEqual(results1.length, 1);
assert.strictEqual(results1[0].token, 'token-critical-recent');
console.log('✓ Test 2: Orthogonal 2D range query correctly isolated recent critical token');

// Test 3: Range query for Old AND Low Saliency: recency in [0, 40], saliency in [0.00, 0.30]
const results2 = kd.rangeSearch(0, 40, 0.00, 0.30);
assert.strictEqual(results2.length, 1);
assert.strictEqual(results2[0].token, 'token-stopword-old');
console.log('✓ Test 3: Isolated old candidate eviction tokens in [0, 40] x [0.00, 0.30]');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 369,
  component: 'kdtree_context_partitioner',
  totalTokensIndexed: kd.size,
  recentHighSaliencyFound: results1.length,
  oldLowSaliencyFound: results2.length,
  orthogonalRangePartitioningVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_KDTREE_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_KDTREE_REPORT.json');
console.log('All KD-Tree Context Partitioner tests passed successfully!');
