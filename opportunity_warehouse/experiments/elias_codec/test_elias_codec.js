const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { EliasCodec, BitStreamReader } = require('./lib/elias_codec');

console.log('Testing Elias Gamma/Delta Codec...');

// Test 1: Single number roundtrips
for (let n = 1; n <= 32; n++) {
  const encoded = EliasCodec.encodeGamma(n);
  const reader = new BitStreamReader(encoded);
  const decoded = EliasCodec.decodeGamma(reader);
  assert.strictEqual(decoded, n);
}
console.log('✓ Test 1: Exact roundtrip verified for integers 1..32');

// Test 2: Sequence of power-law token frequencies
const frequencies = [1, 2, 1, 4, 1, 8, 3, 1, 16, 2, 1, 32];
const stream = EliasCodec.encodeArray(frequencies);
const decodedArr = EliasCodec.decodeArray(stream, frequencies.length);
assert.deepStrictEqual(decodedArr, frequencies);
console.log('✓ Test 2: Array of 12 token frequencies encoded into ' + stream.length + ' bits');

// Test 3: Bit efficiency vs 32-bit integers
const rawBits = frequencies.length * 32; // 384 bits
const compressedBits = stream.length;   // ~ 50 bits
assert.ok(compressedBits < rawBits * 0.25);
console.log('✓ Test 3: Bit compression achieved: ' + (100 - (compressedBits / rawBits * 100)).toFixed(1) + '% space reduction');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 333,
  component: 'elias_codec',
  integersEncoded: frequencies.length,
  rawBits,
  compressedBits,
  savingsPercent: (100 - (compressedBits / rawBits * 100)).toFixed(1),
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_ELIAS_CODEC_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_ELIAS_CODEC_REPORT.json');
console.log('All Elias Codec tests passed successfully!');
