const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { LZ4FrameCodec } = require('./lib/lz4_frame_codec');

console.log('Testing LZ4 Frame Codec...');

const codec = new LZ4FrameCodec(4);

// Test 1: Simple text roundtrip
const text1 = 'symphony autonomous agent workflow for context trimming';
const comp1 = codec.compress(text1);
const decomp1 = codec.decompress(comp1.payload);
assert.strictEqual(decomp1, text1);
console.log('✓ Test 1: Basic text exact lossless roundtrip verified');

// Test 2: Highly repetitive prompt text
const repeatPhrase = 'system instruction: preserve strict invariants and zero spend. ';
const text2 = repeatPhrase.repeat(20);
const comp2 = codec.compress(text2);
const decomp2 = codec.decompress(comp2.payload);
assert.strictEqual(decomp2, text2);
assert.ok(comp2.compressedBytes < comp2.originalBytes);
console.log('✓ Test 2: Repetitive context compressed from ' + comp2.originalBytes + ' to ' + comp2.compressedBytes + ' bytes (' + (comp2.compressionRatio * 100).toFixed(1) + '% savings)');

// Test 3: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 313,
  component: 'lz4_frame_codec',
  originalBytes: comp2.originalBytes,
  compressedBytes: comp2.compressedBytes,
  compressionRatio: comp2.compressionRatio,
  losslessRoundtripVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_LZ4_FRAME_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_LZ4_FRAME_REPORT.json');
console.log('All LZ4 Frame Codec tests passed successfully!');
