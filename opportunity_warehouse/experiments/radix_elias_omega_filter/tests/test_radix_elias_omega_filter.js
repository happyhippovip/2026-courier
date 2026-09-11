const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixEliasOmegaFilter } = require('../lib/radix_elias_omega_filter');

console.log('Testing Radix Elias-Omega Universal Bitvector Filter...');
const filter = new RadixEliasOmegaFilter();

const sampleTokens = [1, 2, 4, 8, 16, 31, 64];
filter.build(sampleTokens);
assert.ok(filter.bitstream.length > 0);
console.log('✓ Test 1: Tokens Elias-Omega encoded (bits:', filter.bitstream.length, ')');

const decoded = filter.decodeOmega(filter.bitstream);
assert.deepStrictEqual(decoded, sampleTokens);
console.log('✓ Test 2: Elias-Omega roundtrip decoded exactly matches input array bit-for-bit');

const report = {
  test: 'RADIX_ELIAS_OMEGA_FILTER',
  passed: true,
  tokenCount: sampleTokens.length,
  bitLength: filter.bitstream.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_RADIX_ELIAS_OMEGA_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 3: Evidence report written to SAMPLE_RADIX_ELIAS_OMEGA_REPORT.json');
console.log('All Radix Elias-Omega Filter tests passed successfully!');
