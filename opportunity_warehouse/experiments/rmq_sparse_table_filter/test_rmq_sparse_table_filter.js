const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { RMQSparseTableFilter } = require('./lib/rmq_sparse_table_filter');

console.log('Testing RMQ Sparse Table Filter...');

const values = [42, 17, 88, 5, 91, 12, 33, 7, 60, 2];
const rmq = new RMQSparseTableFilter(values);

// Test 1: Full range query
const minFull = rmq.queryMin(0, values.length - 1);
assert.strictEqual(minFull.value, 2);
assert.strictEqual(minFull.index, 9);

const maxFull = rmq.queryMax(0, values.length - 1);
assert.strictEqual(maxFull.value, 91);
assert.strictEqual(maxFull.index, 4);
console.log('✓ Test 1: Full range min (2) and max (91) queries verified');

// Test 2: Sub-window queries
const minSub = rmq.queryMin(1, 4); // values: 17, 88, 5, 91
assert.strictEqual(minSub.value, 5);
assert.strictEqual(minSub.index, 3);

const maxSub = rmq.queryMax(5, 8); // values: 12, 33, 7, 60
assert.strictEqual(maxSub.value, 60);
assert.strictEqual(maxSub.index, 8);
console.log('✓ Test 2: Sub-window range min/max queries verified');

// Test 3: Single element boundary query (L === R)
const single = rmq.querySpan(5, 5);
assert.strictEqual(single.min.value, 12);
assert.strictEqual(single.max.value, 12);
assert.strictEqual(single.spread, 0);
console.log('✓ Test 3: Single element boundary query verified');

// Test 4: Verify 20 random ranges against ground-truth slice
for (let iter = 0; iter < 20; iter++) {
  const L = Math.floor(Math.random() * (values.length - 1));
  const R = L + Math.floor(Math.random() * (values.length - L));
  const slice = values.slice(L, R + 1);
  const expectedMin = Math.min(...slice);
  const expectedMax = Math.max(...slice);

  const resMin = rmq.queryMin(L, R);
  const resMax = rmq.queryMax(L, R);

  assert.strictEqual(resMin.value, expectedMin, 'Range [' + L + '..' + R + '] min mismatch');
  assert.strictEqual(resMax.value, expectedMax, 'Range [' + L + '..' + R + '] max mismatch');
}
console.log('✓ Test 4: 20 random range queries verified 100% against ground truth');

// Test 5: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_RMQ_SPARSE_TABLE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 529,
  metrics: rmq.getMetrics(),
  sampleValues: values,
  testSpan: rmq.querySpan(0, values.length - 1),
  verdict: 'RMQ_SPARSE_TABLE_FILTER_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_RMQ_SPARSE_TABLE_REPORT.json');

console.log('All RMQ Sparse Table Filter tests passed successfully!');
