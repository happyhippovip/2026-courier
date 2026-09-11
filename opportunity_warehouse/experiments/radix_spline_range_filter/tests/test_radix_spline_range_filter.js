const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixSplineRangeFilter } = require('../lib/radix_spline_range_filter');

console.log('Testing Radix Spline Range Filter...');

const filter = new RadixSplineRangeFilter(2);
const sortedKeys = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
filter.build(sortedKeys);

// Test 1: Exact search
assert.strictEqual(filter.search(30), 2);
assert.strictEqual(filter.search(80), 7);
assert.strictEqual(filter.search(100), 9);
console.log('✓ Test 1: Point lookups accurately localized via spline approximation');

// Test 2: Range Query
const inRange = filter.rangeQuery(35, 75);
assert.deepStrictEqual(inRange, [40, 50, 60, 70]);
console.log('✓ Test 2: Range query [35..75] accurately returned elements [40, 50, 60, 70]');

// Test 3: Missing key
assert.strictEqual(filter.search(25), null);
assert.strictEqual(filter.search(999), null);
console.log('✓ Test 3: Missing elements correctly return null');

// Test 4: Evidence report export
const evidenceReport = {
  experiment: 'radix_spline_range_filter',
  timestamp: new Date().toISOString(),
  metrics: filter.getMetrics(),
  sampleRange: inRange,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_SPLINE_RANGE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_RADIX_SPLINE_RANGE_REPORT.json');

console.log('All Radix Spline Range Filter tests passed successfully!');
