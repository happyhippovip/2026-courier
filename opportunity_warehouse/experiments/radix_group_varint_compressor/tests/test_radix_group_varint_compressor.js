const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixGroupVarintCompressor } = require('../lib/radix_group_varint_compressor');

console.log('Testing Radix Group-Varint Compressor...');
const compressor = new RadixGroupVarintCompressor();

const sampleTokens = [5, 255, 1024, 70000, 12, 1, 0, 999999, 42];
const buf = compressor.compress(sampleTokens);
assert.ok(buf.length > 0);

const decoded = compressor.decompress(buf);
assert.deepStrictEqual(decoded, sampleTokens);

const stats = compressor.calculateStats(sampleTokens);
assert.strictEqual(stats.tokenCount, sampleTokens.length);
assert.ok(stats.compressedBytes < stats.rawBytes);

const report = {
  experiment: 'radix_group_varint_compressor',
  status: 'VERIFIED',
  testSuite: 'test_radix_group_varint_compressor',
  stats: stats,
  encodedSampleLength: buf.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(
  path.join(__dirname, 'SAMPLE_RADIX_GROUP_VARINT_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);

console.log('✓ Radix Group-Varint Compressor verified successfully.');
