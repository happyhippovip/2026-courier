const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixBitVectorRLECompressor } = require('../lib/radix_bitvector_rle_compressor');

console.log('Testing Radix Bit-Vector RLE Compressor...');
const compressor = new RadixBitVectorRLECompressor();

// Test sparse bitstring with long runs
const original = '0'.repeat(250) + '1'.repeat(10) + '0'.repeat(500) + '1' + '0'.repeat(50);
const buf = compressor.compress(original);
assert.ok(buf.length > 0);

const decoded = compressor.decompress(buf);
assert.strictEqual(decoded, original);

const stats = compressor.calculateStats(original);
assert.strictEqual(stats.totalBits, original.length);
assert.ok(stats.totalRuns < 10);

const report = {
  experiment: 'radix_bitvector_rle_compressor',
  status: 'VERIFIED',
  testSuite: 'test_radix_bitvector_rle_compressor',
  stats: stats,
  encodedLength: buf.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(
  path.join(__dirname, 'SAMPLE_RADIX_BITVECTOR_RLE_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);

console.log('✓ Radix Bit-Vector RLE Compressor verified successfully.');
