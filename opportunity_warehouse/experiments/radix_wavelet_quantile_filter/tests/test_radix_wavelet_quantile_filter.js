const { RadixWaveletQuantileFilter } = require('../lib/radix_wavelet_quantile_filter');
const assert = require('assert');
const path = require('path');

console.log('Testing Radix Wavelet Range Quantile Filter...');

const filter = new RadixWaveletQuantileFilter();

// Test 1: Build on empty sequence
filter.build([]);
assert.strictEqual(filter.quantile(0, 0, 0), null);
assert.strictEqual(filter.rangeCount(0, 0, 10, 20), 0);
console.log('✓ Test 1: Empty sequence bounds handled cleanly');

// Test 2: Standard sequence quantile queries
// Indices:      0   1   2   3   4   5   6   7   8
const tokens = [15, 30,  5, 45, 20, 10, 60, 25, 40];
filter.build(tokens);

// In range [0, 8] (entire array sorted: [5, 10, 15, 20, 25, 30, 40, 45, 60])
assert.strictEqual(filter.quantile(0, 8, 0), 5, 'k=0 should be min: 5');
assert.strictEqual(filter.quantile(0, 8, 4), 25, 'k=4 should be median: 25');
assert.strictEqual(filter.quantile(0, 8, 8), 60, 'k=8 should be max: 60');
console.log('✓ Test 2: Full range quantile queries verified');

// Test 3: Subrange quantile queries
// Subrange [2, 6]: [5, 45, 20, 10, 60] -> sorted: [5, 10, 20, 45, 60]
assert.strictEqual(filter.quantile(2, 6, 0), 5, 'Subrange k=0 must be 5');
assert.strictEqual(filter.quantile(2, 6, 2), 20, 'Subrange k=2 must be 20');
assert.strictEqual(filter.quantile(2, 6, 4), 60, 'Subrange k=4 must be 60');
console.log('✓ Test 3: Subrange [2..6] quantiles verified');

// Test 4: Range counting in subrange
// In subrange [0, 8], values between 15 and 35: [15, 30, 20, 25] -> count: 4
const countA = filter.rangeCount(0, 8, 15, 35);
assert.strictEqual(countA, 4, 'Range count [15..35] must be 4');

// In subrange [2, 6]: [5, 45, 20, 10, 60], values between 10 and 50: [45, 20, 10] -> count: 3
const countB = filter.rangeCount(2, 6, 10, 50);
assert.strictEqual(countB, 3, 'Subrange count [10..50] must be 3');
console.log('✓ Test 4: Range frequency counting verified');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_WAVELET_QUANTILE_REPORT.json');
const report = filter.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'radix_wavelet_quantile_filter');
assert.strictEqual(report.tokenCount, 9);
console.log('✓ Test 5: Evidence report written to SAMPLE_RADIX_WAVELET_QUANTILE_REPORT.json');

console.log('All Radix Wavelet Range Quantile Filter tests passed successfully!');
