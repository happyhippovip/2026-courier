const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { RankPairingHeapFilter } = require('./lib/rank_pairing_heap_filter');

console.log('Testing Rank-Pairing Heap Filter...');

const heap = new RankPairingHeapFilter();

// Test 1: Insertions and findMin
const nodes = [];
const values = [50, 20, 80, 10, 40, 5, 90, 30];
values.forEach((v, idx) => {
  nodes.push(heap.insert(v, 'token_' + idx));
});

assert.strictEqual(heap.count, values.length);
assert.strictEqual(heap.findMin().key, 5);
assert.strictEqual(heap.findMin().value, 'token_5');
console.log('✓ Test 1: Inserted ' + values.length + ' elements; correct minimum detected (5)');

// Test 2: decreaseKey operation
// Decrease node with key 80 (nodes[2]) to 1
heap.decreaseKey(nodes[2], 1);
assert.strictEqual(heap.findMin().key, 1);
assert.strictEqual(heap.findMin().value, 'token_2');
console.log('✓ Test 2: decreaseKey to 1 immediately escalated to new minimum');

// Test 3: Sequential deleteMin extracts monotonic ascending order
const sorted = heap.extractSorted();
assert.strictEqual(sorted.length, values.length);
for (let i = 1; i < sorted.length; i++) {
  assert(sorted[i].key >= sorted[i - 1].key, 'Extracted sequence must be sorted');
}
assert.strictEqual(sorted[0].key, 1);
assert.strictEqual(sorted[sorted.length - 1].key, 90);
console.log('✓ Test 3: Sequential deleteMin verified sorted ordering 100% exact');

// Test 4: Re-insert and boundary decreaseKey validation
const h2 = new RankPairingHeapFilter();
const n1 = h2.insert(100, 't1');
assert.throws(() => {
  h2.decreaseKey(n1, 150); // increase key should throw
}, /strictly smaller/, 'Increasing key must throw');
console.log('✓ Test 4: Invalid key increase rejected fail-closed');

// Test 5: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_RANK_PAIRING_HEAP_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 533,
  metrics: heap.getMetrics(),
  extractedSorted: sorted,
  verdict: 'RANK_PAIRING_HEAP_FILTER_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_RANK_PAIRING_HEAP_REPORT.json');

console.log('All Rank-Pairing Heap Filter tests passed successfully!');
