const { RadixInterpolativeFilter } = require('../lib/radix_interpolative_filter');
const assert = require('assert');
const path = require('path');

console.log('Testing Radix Interpolative Filter...');

const filter = new RadixInterpolativeFilter(4);

// Test 1: Empty filter bounds
filter.build([]);
assert.strictEqual(filter.contains(10), false);
assert.deepStrictEqual(filter.rangeQuery(0, 100), []);
console.log('✓ Test 1: Empty sequence bounds verified');

// Test 2: Ingest sorted keys and verify contains
const keys = [10, 25, 40, 55, 70, 85, 100, 120, 150];
filter.build(keys);

for (const k of keys) {
  assert.strictEqual(filter.contains(k), true, 'Must find key ' + k);
}
assert.strictEqual(filter.contains(5), false);
assert.strictEqual(filter.contains(45), false);
assert.strictEqual(filter.contains(200), false);
console.log('✓ Test 2: Interpolative lookup verified on existing and missing keys');

// Test 3: Range query [30..90]
const rangeSlice = filter.rangeQuery(30, 90);
assert.deepStrictEqual(rangeSlice, [40, 55, 70, 85]);
console.log('✓ Test 3: Range query [30..90] returned exact slice');

// Test 4: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_INTERPOLATIVE_REPORT.json');
const report = filter.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'radix_interpolative_filter');
assert.strictEqual(report.keyCount, 9);
console.log('✓ Test 4: Evidence report written to SAMPLE_RADIX_INTERPOLATIVE_REPORT.json');

console.log('All Radix Interpolative Filter tests passed successfully!');
