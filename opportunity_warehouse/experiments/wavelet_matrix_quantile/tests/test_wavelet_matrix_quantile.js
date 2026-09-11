const { WaveletMatrixQuantile } = require('../lib/wavelet_matrix_quantile');
const fs = require('fs');
const path = require('path');

console.log('Testing Succinct Wavelet Matrix Quantile Evaluator...');

// Token sequence: 16 integers in [0 .. 63] (levels = 6)
const tokens = [42, 17, 5, 60, 23, 17, 31, 8, 55, 12, 42, 9, 3, 27, 49, 14];
const wmq = new WaveletMatrixQuantile(tokens, 63);

// Test 1: Full range quantile verification against sorted ground truth
const sorted = tokens.slice().sort((a, b) => a - b);
// sorted: [3, 5, 8, 9, 12, 14, 17, 17, 23, 27, 31, 42, 42, 49, 55, 60]

const minVal = wmq.quantile(0, tokens.length - 1, 0);
const maxVal = wmq.quantile(0, tokens.length - 1, tokens.length - 1);
const medianVal = wmq.median(0, tokens.length - 1);

console.log('✓ Test 1: Full range min: ' + minVal + ' (expected ' + sorted[0] + '), max: ' + maxVal + ' (expected ' + sorted[sorted.length - 1] + '), median: ' + medianVal);
if (minVal !== sorted[0] || maxVal !== sorted[sorted.length - 1] || medianVal !== sorted[Math.floor((tokens.length - 1) / 2)]) {
  throw new Error('Full range quantile mismatch');
}

// Test 2: Subrange quantile check on range [3 .. 10]
// Subrange: [60, 23, 17, 31, 8, 55, 12, 42]
// Sorted subrange: [8, 12, 17, 23, 31, 42, 55, 60]
const subK0 = wmq.quantile(3, 10, 0);
const subK3 = wmq.quantile(3, 10, 3);
const subK7 = wmq.quantile(3, 10, 7);

console.log('✓ Test 2: Subrange [3..10] k=0: ' + subK0 + ' (exp 8), k=3: ' + subK3 + ' (exp 23), k=7: ' + subK7 + ' (exp 60)');
if (subK0 !== 8 || subK3 !== 23 || subK7 !== 60) {
  throw new Error('Subrange quantile failed');
}

// Test 3: Compression statistics verification
const stats = wmq.getCompressionStats();
console.log('✓ Test 3: Wavelet Matrix compression ratio: ' + stats.compressionRatio + ' (' + stats.totalBits + ' bits vs ' + stats.rawInt32Bits + ' bits)');
if (stats.bitLevels !== 6) {
  throw new Error('Expected 6 bit levels for maxVal=63, got ' + stats.bitLevels);
}

// Write evidence report
const report = {
  experiment: 'wavelet_matrix_quantile',
  phase: 469,
  timestamp: new Date().toISOString(),
  sequenceLength: tokens.length,
  alphabetMax: 63,
  levels: wmq.levels,
  minFound: minVal,
  maxFound: maxVal,
  medianFound: medianVal,
  subrangeQuery: { range: [3, 10], k0: subK0, k3: subK3, k7: subK7 },
  stats,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_WAVELET_MATRIX_QUANTILE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_WAVELET_MATRIX_QUANTILE_REPORT.json');

console.log('All Wavelet Matrix Quantile tests passed successfully!');
