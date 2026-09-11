const { RadixExpGolombFilter } = require('../lib/radix_exp_golomb_filter');
const assert = require('assert');
const path = require('path');

console.log('Testing Radix Exp-Golomb Filter...');

const filter = new RadixExpGolombFilter(1);

// Test 1: Empty input
filter.build([]);
assert.deepStrictEqual(filter.decode(), []);
assert.strictEqual(filter.queryCount(10), 0);
console.log('✓ Test 1: Empty input handled cleanly');

// Test 2: Ingest varied integers with k=1
const tokens = [0, 1, 2, 5, 10, 25, 50, 100, 0, 5];
filter.build(tokens, 1);
const decoded = filter.decode(1);
assert.deepStrictEqual(decoded, tokens, 'Lossless roundtrip must restore exact tokens');
console.log('✓ Test 2: Exp-Golomb k=1 roundtrip verified (Tokens: ' + tokens.length + ')');

// Test 3: Frequency counting
const count0 = filter.queryCount(0);
assert.strictEqual(count0, 2, 'Token 0 occurs twice');
const count5 = filter.queryCount(5);
assert.strictEqual(count5, 2, 'Token 5 occurs twice');
console.log('✓ Test 3: Token frequency query verified');

// Test 4: Higher order k=2
filter.build(tokens, 2);
const decodedK2 = filter.decode(2);
assert.deepStrictEqual(decodedK2, tokens, 'Lossless roundtrip must restore exact tokens for k=2');
console.log('✓ Test 4: Exp-Golomb k=2 roundtrip confirmed');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_EXP_GOLOMB_REPORT.json');
const report = filter.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'radix_exp_golomb_filter');
assert.strictEqual(report.tokenCount, 10);
console.log('✓ Test 5: Evidence report written to SAMPLE_RADIX_EXP_GOLOMB_REPORT.json');

console.log('All Radix Exp-Golomb Filter tests passed successfully!');
