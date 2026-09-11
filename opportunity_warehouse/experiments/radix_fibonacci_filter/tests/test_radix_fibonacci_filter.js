const { RadixFibonacciFilter } = require('../lib/radix_fibonacci_filter');
const assert = require('assert');
const path = require('path');

console.log('Testing Radix Fibonacci Filter...');

const filter = new RadixFibonacciFilter();

// Test 1: Empty input
filter.build([]);
assert.deepStrictEqual(filter.decode(), []);
assert.strictEqual(filter.queryRank(5), 0);
console.log('✓ Test 1: Empty input handled cleanly');

// Test 2: Monotonic integer sequences
const tokens = [0, 1, 5, 12, 40, 100, 3, 0, 5, 12];
filter.build(tokens);
const decoded = filter.decode();
assert.deepStrictEqual(decoded, tokens, 'Lossless roundtrip must restore exact tokens');
console.log('✓ Test 2: Fibonacci universal coding roundtrip verified (Tokens: ' + tokens.length + ')');

// Test 3: Rank query
const rank5 = filter.queryRank(5);
assert.strictEqual(rank5, 2, 'Token 5 occurs twice');
const rank0 = filter.queryRank(0);
assert.strictEqual(rank0, 2, 'Token 0 occurs twice');
console.log('✓ Test 3: Rank queries verified across decoded stream');

// Test 4: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_FIBONACCI_REPORT.json');
const report = filter.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'radix_fibonacci_filter');
assert.strictEqual(report.tokenCount, 10);
console.log('✓ Test 4: Evidence report written to SAMPLE_RADIX_FIBONACCI_REPORT.json');

console.log('All Radix Fibonacci Filter tests passed successfully!');
