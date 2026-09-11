const { RadixEliasFanoFilter } = require('../lib/radix_elias_fano_filter');
const assert = require('assert');
const path = require('path');

console.log('Testing Radix Elias-Fano Filter...');

const filter = new RadixEliasFanoFilter(4);

// Test 1: Empty input
filter.build([]);
assert.strictEqual(filter.contains(5), false);
assert.deepStrictEqual(filter.rangeQuery(0, 100), []);
console.log('✓ Test 1: Empty input handled cleanly');

// Test 2: Ingest monotonic sequences
const keys = [2, 7, 15, 23, 45, 68, 92, 110, 150];
filter.build(keys);

for (const k of keys) {
  assert.strictEqual(filter.contains(k), true, 'Must find key ' + k);
}
assert.strictEqual(filter.contains(3), false);
assert.strictEqual(filter.contains(50), false);
assert.strictEqual(filter.contains(200), false);
console.log('✓ Test 2: Elias-Fano lookups verified on existing and non-existing keys');

// Test 3: Range queries
const inRange = filter.rangeQuery(20, 100);
assert.deepStrictEqual(inRange, [23, 45, 68, 92]);
console.log('✓ Test 3: Range query [20..100] returned exact slice');

// Test 4: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_ELIAS_FANO_REPORT.json');
const report = filter.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'radix_elias_fano_filter');
assert.strictEqual(report.keyCount, 9);
console.log('✓ Test 4: Evidence report written to SAMPLE_RADIX_ELIAS_FANO_REPORT.json');

console.log('All Radix Elias-Fano Filter tests passed successfully!');
