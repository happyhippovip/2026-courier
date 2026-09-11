const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixVByteCompressor } = require('../lib/radix_vbyte_compressor');

console.log('Testing Radix Variable-Byte Integer Compressor...');
const compressor = new RadixVByteCompressor();

const sampleTokens = [0, 1, 127, 128, 255, 16383, 16384, 1000000];
const buf = compressor.compress(sampleTokens);
assert.ok(buf.length > 0);

const decoded = compressor.decompress(buf);
assert.deepStrictEqual(decoded, sampleTokens);

const stats = compressor.calculateStats(sampleTokens);
assert.strictEqual(stats.tokenCount, sampleTokens.length);
assert.ok(stats.compressedBytes < stats.rawBytes);

const report = {
  experiment: 'radix_vbyte_compressor',
  status: 'VERIFIED',
  testSuite: 'test_radix_vbyte_compressor',
  stats: stats,
  encodedSampleLength: buf.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(
  path.join(__dirname, 'SAMPLE_RADIX_VBYTE_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);

console.log('✓ Radix Variable-Byte Integer Compressor verified successfully.');
