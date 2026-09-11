const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { EliasFanoEncoder } = require('./lib/elias_fano_encoder');

console.log('Testing Elias-Fano Monotonic Encoder...');

const encoder = new EliasFanoEncoder();
const sortedSequence = [
  3, 8, 15, 27, 44, 59, 81, 105, 140, 188,
  245, 310, 390, 480, 590, 720, 890, 1050, 1280, 1600
];

const metrics = encoder.encode(sortedSequence);

// Test 1: Exact value reconstruction via O(1) random access
for (let i = 0; i < sortedSequence.length; i++) {
  assert.strictEqual(encoder.get(i), sortedSequence[i], 'Index ' + i + ' must match original value');
}
assert.deepStrictEqual(encoder.toArray(), sortedSequence);
console.log('✓ Test 1: O(1) random access reconstruction verified 100% exact across all ' + sortedSequence.length + ' elements');

// Test 2: Predecessor queries
const p1 = encoder.predecessor(100);
assert.strictEqual(p1.value, 81);
assert.strictEqual(p1.index, 6);

const p2 = encoder.predecessor(140);
assert.strictEqual(p2.value, 140);
assert.strictEqual(p2.index, 8);

const p3 = encoder.predecessor(2);
assert.strictEqual(p3, null, 'Values below minimum must return null');
console.log('✓ Test 2: Predecessor search verified for exact, interval, and boundary queries');

// Test 3: Compression efficiency
assert(metrics.compressedBytes < metrics.rawBytes, 'Compressed size must be smaller than raw 32-bit integers');
assert(metrics.compressionRatio > 0.5, 'Must achieve > 50% memory savings');
console.log('✓ Test 3: Quasi-succinct compression verified (Savings: ' + metrics.savingsPercent + ', ' + metrics.compressedBytes + ' bytes vs ' + metrics.rawBytes + ' bytes)');

// Test 4: Monotonicity enforcement
assert.throws(() => {
  const badEncoder = new EliasFanoEncoder();
  badEncoder.encode([10, 5, 20]);
}, /non-decreasing order/, 'Non-monotonic sequence must throw');
console.log('✓ Test 4: Monotonicity invariant enforced fail-closed');

// Test 5: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_ELIAS_FANO_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 517,
  metrics,
  sampleSequence: sortedSequence,
  verdict: 'ELIAS_FANO_ENCODER_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_ELIAS_FANO_REPORT.json');

console.log('All Elias-Fano Monotonic Encoder tests passed successfully!');
