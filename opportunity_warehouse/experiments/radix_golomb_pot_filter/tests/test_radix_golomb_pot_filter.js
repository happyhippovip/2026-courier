const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixGolombPotFilter } = require('../lib/radix_golomb_pot_filter');

console.log('Testing Radix Golomb Power-of-Two Filter...');
const filter = new RadixGolombPotFilter(3);

const sampleTokens = [0, 1, 5, 8, 14, 25, 42, 100];
filter.build(sampleTokens);
assert.ok(filter.bitstream.length > 0);
console.log('✓ Test 1: Tokens Golomb-encoded with power-of-two parameter k=3 (bits:', filter.bitstream.length, ')');

const decoded = filter.decode(filter.bitstream);
assert.deepStrictEqual(decoded, sampleTokens);
console.log('✓ Test 2: Golomb power-of-two roundtrip matches input sequence bit-for-bit');

const report = {
  test: 'RADIX_GOLOMB_POT_FILTER',
  passed: true,
  tokenCount: sampleTokens.length,
  bitLength: filter.bitstream.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_RADIX_GOLOMB_POT_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 3: Evidence report written to SAMPLE_RADIX_GOLOMB_POT_REPORT.json');
console.log('All Radix Golomb Power-of-Two Filter tests passed successfully!');
