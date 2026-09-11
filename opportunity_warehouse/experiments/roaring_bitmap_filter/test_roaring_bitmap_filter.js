const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { RoaringBitmap } = require('./lib/roaring_bitmap_filter');

console.log('Testing Context Window Token Bounded Roaring BitMap Index Filter...');

const bm1 = new RoaringBitmap();

// Test 1: Sparse insertions in multiple chunks (ArrayContainer verification)
const sparseTokens = [10, 42, 999, 65546, 65550, 131072, 131080];
sparseTokens.forEach(t => bm1.add(t));

assert.strictEqual(bm1.cardinality(), 7);
sparseTokens.forEach(t => {
  assert.strictEqual(bm1.contains(t), true, 'Must contain token ' + t);
});
assert.strictEqual(bm1.contains(11), false);
assert.strictEqual(bm1.contains(65547), false);
console.log('✓ Test 1: Sparse insertions into ArrayContainers verified');

// Test 2: Dense insertions crossing threshold (> 4096) to trigger BitsetContainer
const bmDense = new RoaringBitmap();
for (let i = 0; i <= 4100; i++) {
  bmDense.add(i); // Chunk 0
}
assert.strictEqual(bmDense.cardinality(), 4101);
const chunk0 = bmDense.chunks.get(0);
assert.strictEqual(chunk0.type, 'BITSET', 'Container must have converted to BITSET');
assert.strictEqual(bmDense.contains(0), true);
assert.strictEqual(bmDense.contains(2048), true);
assert.strictEqual(bmDense.contains(4100), true);
assert.strictEqual(bmDense.contains(4101), false);
console.log('✓ Test 2: Dense insertions automatically promoted to BitsetContainer');

// Test 3: Set operations (Intersection and Union)
const bm2 = new RoaringBitmap();
bm2.add(42);
bm2.add(999);
bm2.add(12345);
bm2.add(65550);

const intersection = bm1.and(bm2);
assert.strictEqual(intersection.cardinality(), 3);
assert.strictEqual(intersection.contains(42), true);
assert.strictEqual(intersection.contains(999), true);
assert.strictEqual(intersection.contains(65550), true);
assert.strictEqual(intersection.contains(10), false);

const union = bm1.or(bm2);
assert.strictEqual(union.cardinality(), 8);
assert.strictEqual(union.contains(12345), true);
console.log('✓ Test 3: Bitwise Intersection (AND) and Union (OR) verified');

// Test 4: Memory compression metrics
const metrics = bm1.getMetrics();
assert(metrics.roaringBytes < metrics.rawArrayBytes, 'Roaring bitmap must achieve compression');
console.log('✓ Test 4: Compression savings verified (Savings: ' + metrics.savingsPercent + ', ' + metrics.roaringBytes + ' bytes vs ' + metrics.rawArrayBytes + ' bytes)');

// Test 5: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_ROARING_BITMAP_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 505,
  metrics,
  sampleQueries: {
    intersectionCardinality: intersection.cardinality(),
    unionCardinality: union.cardinality()
  },
  verdict: 'ROARING_BITMAP_FILTER_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_ROARING_BITMAP_REPORT.json');

console.log('All Roaring BitMap Index Filter tests passed successfully!');
