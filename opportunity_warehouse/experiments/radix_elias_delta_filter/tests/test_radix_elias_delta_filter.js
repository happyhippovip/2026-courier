const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixEliasDeltaFilter } = require('../lib/radix_elias_delta_filter');

console.log('Testing Radix Elias-Delta Universal Bitvector Filter...');
const filter = new RadixEliasDeltaFilter();

const sampleTokens = [1, 2, 7, 15, 63, 127, 255];
filter.build(sampleTokens);
assert.ok(filter.bitstream.length > 0);
console.log('✓ Test 1: Tokens Elias-Delta encoded (bits:', filter.bitstream.length, ')');

const decoded = filter.decodeDelta(filter.bitstream);
assert.deepStrictEqual(decoded, sampleTokens);
console.log('✓ Test 2: Elias-Delta roundtrip decoded exactly matches input array bit-for-bit');

const report = {
  test: 'RADIX_ELIAS_DELTA_FILTER',
  passed: true,
  tokenCount: sampleTokens.length,
  bitLength: filter.bitstream.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_RADIX_ELIAS_DELTA_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 3: Evidence report written to SAMPLE_RADIX_ELIAS_DELTA_REPORT.json');
console.log('All Radix Elias-Delta Filter tests passed successfully!');
