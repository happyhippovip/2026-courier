const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { BitSlicedIndex } = require('./lib/bit_sliced_index_filter');

console.log('Testing Bit-Sliced Index (BSI) Filter...');

const bsi = new BitSlicedIndex(8, 128); // 8-bit values (0-255)
const sampleValues = [15, 200, 42, 88, 150, 200, 10, 5, 255, 0, 77, 128];
sampleValues.forEach(v => bsi.append(v));

assert.strictEqual(bsi.length, sampleValues.length);

// Test 1: Value retrieval roundtrip
for (let i = 0; i < sampleValues.length; i++) {
  assert.strictEqual(bsi.getValue(i), sampleValues[i], 'Index ' + i + ' must match original value');
}
console.log('✓ Test 1: Bit-sliced value reconstruction verified 100% exact');

// Test 2: filterGreaterThan threshold evaluation
const threshold = 100;
const expectedGt = [];
sampleValues.forEach((v, idx) => {
  if (v > threshold) expectedGt.push(idx);
});
const bsiGt = bsi.filterGreaterThan(threshold);
assert.deepStrictEqual(bsiGt, expectedGt, 'Filter greater-than must match ground truth');
console.log('✓ Test 2: SIMD-style bitwise filterGreaterThan verified (matched ' + bsiGt.length + ' elements > ' + threshold + ')');

// Test 3: filterRange evaluation
const rangeMin = 40;
const rangeMax = 160;
const expectedRange = [];
sampleValues.forEach((v, idx) => {
  if (v >= rangeMin && v <= rangeMax) expectedRange.push(idx);
});
const bsiRange = bsi.filterRange(rangeMin, rangeMax);
assert.deepStrictEqual(bsiRange, expectedRange);
console.log('✓ Test 3: filterRange [' + rangeMin + '..' + rangeMax + '] verified');

// Test 4: popcount based bit-sliced sum
const expectedSum = sampleValues.reduce((acc, x) => acc + x, 0);
const bsiSum = bsi.sum();
assert.strictEqual(bsiSum, expectedSum, 'Bit-sliced sum must match arithmetic sum');
console.log('✓ Test 4: Bit-sliced slice-popcount sum aggregation verified (' + bsiSum + ' == ' + expectedSum + ')');

// Test 5: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_BIT_SLICED_INDEX_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 509,
  metrics: bsi.getMetrics(),
  sampleValues,
  results: {
    greaterThan100: bsiGt,
    range40to160: bsiRange,
    totalSum: bsiSum
  },
  verdict: 'BIT_SLICED_INDEX_FILTER_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_BIT_SLICED_INDEX_REPORT.json');

console.log('All Bit-Sliced Index Filter tests passed successfully!');
