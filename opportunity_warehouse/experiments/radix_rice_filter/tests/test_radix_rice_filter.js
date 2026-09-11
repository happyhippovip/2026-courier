const { RadixRiceFilter } = require('../lib/radix_rice_filter');
const assert = require('assert');
const path = require('path');

console.log('Testing Radix Rice Filter...');

const filter = new RadixRiceFilter(2);

// Test 1: Empty input
filter.build([]);
assert.deepStrictEqual(filter.decode(), []);
assert.strictEqual(filter.queryCount(5), 0);
console.log('✓ Test 1: Empty input handled cleanly');

// Test 2: Ingest varied integers with k=2
const tokens = [0, 1, 3, 4, 7, 12, 25, 0, 4, 15];
filter.build(tokens, 2);
const decodedK2 = filter.decode(2);
assert.deepStrictEqual(decodedK2, tokens, 'Lossless roundtrip must restore exact tokens with k=2');
console.log('✓ Test 2: Rice k=2 roundtrip verified (Tokens: ' + tokens.length + ')');

// Test 3: Frequency counting
const count4 = filter.queryCount(4);
assert.strictEqual(count4, 2, 'Token 4 occurs twice');
const count0 = filter.queryCount(0);
assert.strictEqual(count0, 2, 'Token 0 occurs twice');
console.log('✓ Test 3: Token frequency counting verified');

// Test 4: Different parameter k=1
filter.build(tokens, 1);
const decodedK1 = filter.decode(1);
assert.deepStrictEqual(decodedK1, tokens, 'Lossless roundtrip must restore exact tokens with k=1');
console.log('✓ Test 4: Rice k=1 roundtrip verified');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_RICE_REPORT.json');
const report = filter.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'radix_rice_filter');
assert.strictEqual(report.tokenCount, 10);
console.log('✓ Test 5: Evidence report written to SAMPLE_RADIX_RICE_REPORT.json');

console.log('All Radix Rice Filter tests passed successfully!');
