const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ZigZagIntegerCompressor } = require('../lib/zigzag_compressor');

const compressor = new ZigZagIntegerCompressor();

// Test 1: ZigZag mapping correctness
assert.strictEqual(compressor.encodeZigZag(0), 0);
assert.strictEqual(compressor.encodeZigZag(-1), 1);
assert.strictEqual(compressor.encodeZigZag(1), 2);
assert.strictEqual(compressor.encodeZigZag(-2), 3);
assert.strictEqual(compressor.encodeZigZag(2), 4);
assert.strictEqual(compressor.decodeZigZag(1), -1);
assert.strictEqual(compressor.decodeZigZag(2), 1);
assert.strictEqual(compressor.decodeZigZag(3), -2);
console.log('✓ Test 1: ZigZag mapping exact bijection verified');

// Test 2: Varint encoding & decoding
const sampleVarints = [0, 1, 127, 128, 300, 16384];
for (const val of sampleVarints) {
  const enc = compressor.encodeVarint(val);
  const dec = compressor.decodeVarint(Buffer.from(enc));
  assert.strictEqual(dec.value, val, 'Varint roundtrip must match for ' + val);
}
console.log('✓ Test 2: LEB128 Varint encode/decode roundtrip verified');

// Test 3: Delta stream compression on sorted/monotonic token indices
// E.g., sequential token positions in context buffer: 100, 102, 105, 106, 110, ...
const tokenPositions = [];
let cur = 1000;
for (let i = 0; i < 200; i++) {
  cur += Math.floor(Math.random() * 5) + 1; // delta between 1 and 5
  tokenPositions.push(cur);
}

const compressedBuffer = compressor.compressDeltas(tokenPositions);
const decompressed = compressor.decompressDeltas(compressedBuffer);

assert.deepStrictEqual(decompressed, tokenPositions, 'Decompressed deltas must match exactly');
const rawBytes = tokenPositions.length * 4; // 32-bit ints = 800 bytes
const compressedBytes = compressedBuffer.length;
assert.ok(compressedBytes < rawBytes * 0.40, 'Compressed size should be < 40% of raw 32-bit array');
const savingsPercent = Number(((1 - compressedBytes / rawBytes) * 100).toFixed(2));
console.log('✓ Test 3: Delta compression achieved ' + savingsPercent + '% savings (' + compressedBytes + ' vs ' + rawBytes + ' bytes)');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_ZIGZAG_COMPRESSION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  itemsCount: tokenPositions.length,
  rawBytes,
  compressedBytes,
  savingsPercent,
  samplePositions: tokenPositions.slice(0, 10),
  sampleHex: compressedBuffer.slice(0, 16).toString('hex')
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_ZIGZAG_COMPRESSION_REPORT.json');

console.log('All ZigZag Integer Compressor tests passed successfully!');
