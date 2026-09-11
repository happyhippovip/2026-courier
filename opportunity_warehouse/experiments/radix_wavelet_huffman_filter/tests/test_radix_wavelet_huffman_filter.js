const { RadixWaveletHuffmanFilter } = require('../lib/radix_wavelet_huffman_filter');
const assert = require('assert');
const path = require('path');

console.log('Testing Radix Wavelet Huffman Filter...');

const filter = new RadixWaveletHuffmanFilter();

// Test 1: Empty input
filter.build([]);
assert.strictEqual(filter.access(0), null);
assert.strictEqual(filter.rank(10, 5), 0);
console.log('✓ Test 1: Empty input handled cleanly');

// Test 2: Frequency-skewed tokens
// Token 10 occurs 10 times, Token 20 occurs 4 times, Token 30 occurs 1 time
const skewed = [10, 10, 10, 20, 10, 10, 20, 10, 30, 10, 10, 20, 10, 10, 20];
filter.build(skewed);

// Most frequent token (10) must have the shortest code length
const len10 = filter.getCodeLength(10);
const len30 = filter.getCodeLength(30);
assert(len10 <= len30, 'Frequent token 10 must have shorter or equal code than rare token 30');
console.log('✓ Test 2: Huffman code length hierarchy verified (len10: ' + len10 + ' <= len30: ' + len30 + ')');

// Test 3: Access verification
for (let i = 0; i < skewed.length; i++) {
  assert.strictEqual(filter.access(i), skewed[i]);
}
console.log('✓ Test 3: Lossless element access verified across stream');

// Test 4: Rank queries
const rank10At5 = filter.rank(10, 5); // in indices [0..5]: [10, 10, 10, 20, 10, 10] -> count: 5
assert.strictEqual(rank10At5, 5, 'Rank of token 10 at index 5 must be 5');
const rank20At6 = filter.rank(20, 6); // [10, 10, 10, 20, 10, 10, 20] -> count: 2
assert.strictEqual(rank20At6, 2, 'Rank of token 20 at index 6 must be 2');
console.log('✓ Test 4: Rank queries verified');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_WAVELET_HUFFMAN_REPORT.json');
const report = filter.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'radix_wavelet_huffman_filter');
assert.strictEqual(report.tokenCount, 15);
console.log('✓ Test 5: Evidence report written to SAMPLE_RADIX_WAVELET_HUFFMAN_REPORT.json');

console.log('All Radix Wavelet Huffman Filter tests passed successfully!');
