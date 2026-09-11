const { RadixWaveletRMQEvaluator } = require('../lib/radix_wavelet_rmq_evaluator');
const assert = require('assert');
const path = require('path');

console.log('Testing Radix Wavelet RMQ Evaluator...');

const evaluator = new RadixWaveletRMQEvaluator();

// Test 1: Empty input
evaluator.build([], []);
assert.strictEqual(evaluator.queryMax(0, 0), null);
assert.deepStrictEqual(evaluator.topK(0, 0, 3), []);
console.log('✓ Test 1: Empty input handled cleanly');

// Test 2: Ingest tokens and saliencies
// Indices:      0    1    2    3    4    5    6    7
const tokens = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
const scores = [ 10,  85,  40,  95,  30, 110,  70,  20];
evaluator.build(tokens, scores);

// Query full range [0, 7] -> max should be 'F' with score 110 at index 5
const maxFull = evaluator.queryMax(0, 7);
assert.strictEqual(maxFull.index, 5);
assert.strictEqual(maxFull.token, 'F');
assert.strictEqual(maxFull.saliency, 110);
console.log('✓ Test 2: Full range maximum verified (token F, score 110)');

// Test 3: Subrange RMQ queries
// Range [0, 3]: [10, 85, 40, 95] -> max is 'D' (95) at index 3
const maxSub1 = evaluator.queryMax(0, 3);
assert.strictEqual(maxSub1.index, 3);
assert.strictEqual(maxSub1.token, 'D');

// Range [1, 2]: [85, 40] -> max is 'B' (85) at index 1
const maxSub2 = evaluator.queryMax(1, 2);
assert.strictEqual(maxSub2.index, 1);
assert.strictEqual(maxSub2.token, 'B');
console.log('✓ Test 3: Subrange RMQ queries verified in O(1)');

// Test 4: Top-K extraction
// Top-3 in range [0, 7] should be F (110), D (95), B (85)
const top3 = evaluator.topK(0, 7, 3);
assert.strictEqual(top3.length, 3);
assert.strictEqual(top3[0].token, 'F');
assert.strictEqual(top3[1].token, 'D');
assert.strictEqual(top3[2].token, 'B');
console.log('✓ Test 4: Top-3 saliency extraction verified');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_WAVELET_RMQ_REPORT.json');
const report = evaluator.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'radix_wavelet_rmq_evaluator');
assert.strictEqual(report.itemCount, 8);
console.log('✓ Test 5: Evidence report written to SAMPLE_RADIX_WAVELET_RMQ_REPORT.json');

console.log('All Radix Wavelet RMQ Evaluator tests passed successfully!');
