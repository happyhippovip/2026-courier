const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixUnarySaliencyFilter } = require('../lib/radix_unary_saliency_filter');

console.log('Testing Radix Unary Saliency Filter...');
const filter = new RadixUnarySaliencyFilter({ radixInterval: 4 });

const sampleTokens = [
  { id: 1, saliencyRank: 3 },
  { id: 2, saliencyRank: 0 },
  { id: 3, saliencyRank: 5 },
  { id: 4, saliencyRank: 1 },
  { id: 5, saliencyRank: 2 },
  { id: 6, saliencyRank: 0 },
  { id: 7, saliencyRank: 4 }
];

filter.encode(sampleTokens);
assert.ok(filter.bitstream.length > 0);
console.log('✓ Test 1: Tokens successfully unary-encoded with radix checkpoints (bits:', filter.bitstream.length, ')');

// Verify exact decoding at checkpoints and arbitrary offsets
assert.strictEqual(filter.decodeAt(0), 3);
assert.strictEqual(filter.decodeAt(1), 0);
assert.strictEqual(filter.decodeAt(2), 5);
assert.strictEqual(filter.decodeAt(3), 1);
assert.strictEqual(filter.decodeAt(4), 2);
assert.strictEqual(filter.decodeAt(5), 0);
assert.strictEqual(filter.decodeAt(6), 4);
console.log('✓ Test 2: Random access decoding via radix checkpoints bit-exact');

const report = {
  test: 'RADIX_UNARY_SALIENCY_FILTER',
  passed: true,
  tokenCount: sampleTokens.length,
  bitLength: filter.bitstream.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_RADIX_UNARY_FILTER_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 3: Evidence report written to SAMPLE_RADIX_UNARY_FILTER_REPORT.json');
console.log('All Radix Unary Saliency Filter tests passed successfully!');
