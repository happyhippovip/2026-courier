const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixFibonacciUniversalFilter } = require('../lib/radix_fibonacci_universal_filter');

console.log('Testing Radix Fibonacci Universal Coding Filter...');
const filter = new RadixFibonacciUniversalFilter();

const originalTokens = [1, 2, 5, 13, 21, 42, 100];
filter.build(originalTokens);
assert.ok(filter.bitstream.length > 0);
console.log('✓ Test 1: Tokens Fibonacci-encoded into bitstream (length:', filter.bitstream.length, 'bits)');

const decoded = filter.decodeStream(filter.bitstream);
assert.deepStrictEqual(decoded, originalTokens);
console.log('✓ Test 2: Lossless self-synchronizing Fibonacci decode matches original sequence bit-for-bit');

const report = {
  test: 'RADIX_FIBONACCI_UNIVERSAL_FILTER',
  passed: true,
  tokenCount: originalTokens.length,
  bitLength: filter.bitstream.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_RADIX_FIBONACCI_UNIVERSAL_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 3: Evidence report written to SAMPLE_RADIX_FIBONACCI_UNIVERSAL_REPORT.json');
console.log('All Radix Fibonacci Universal Coding Filter tests passed successfully!');
