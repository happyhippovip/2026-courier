const { WaveletTreeQuantileFilter } = require('../lib/wavelet_tree_quantile');
const fs = require('fs');
const path = require('path');

console.log('Testing Dynamic Wavelet Tree Quantile Filter...');

// Synthetic stream of token saliencies (integers 0..100)
const tokenStream = [45, 12, 88, 34, 12, 99, 23, 67, 10, 50, 78, 34, 91, 5];
const wt = new WaveletTreeQuantileFilter(tokenStream, 100);

// Test 1: Quantile query over full array
// Sorted tokenStream: [5, 10, 12, 12, 23, 34, 34, 45, 50, 67, 78, 88, 91, 99]
const minVal = wt.quantile(0, tokenStream.length - 1, 0);
const maxVal = wt.quantile(0, tokenStream.length - 1, tokenStream.length - 1);
const medianVal = wt.median(0, tokenStream.length - 1);

console.log('✓ Test 1: Full range min: ' + minVal + ', max: ' + maxVal + ', median: ' + medianVal);
if (minVal !== 5 || maxVal !== 99 || medianVal !== 34) {
  throw new Error('Quantile query on full array failed: min=' + minVal + ', max=' + maxVal + ', med=' + medianVal);
}

// Test 2: Subrange quantile query [2 .. 7]: [88, 34, 12, 99, 23, 67]
// Sorted subrange: [12, 23, 34, 67, 88, 99]
const subK0 = wt.quantile(2, 7, 0); // 12
const subK2 = wt.quantile(2, 7, 2); // 34
const subK5 = wt.quantile(2, 7, 5); // 99
console.log('✓ Test 2: Subrange [2..7] k=0: ' + subK0 + ', k=2: ' + subK2 + ', k=5: ' + subK5);
if (subK0 !== 12 || subK2 !== 34 || subK5 !== 99) {
  throw new Error('Subrange quantile failed');
}

// Test 3: Range count query
// In range [0 .. 13], how many tokens are in [10 .. 40]?
// Tokens: 12, 34, 12, 23, 10, 34 (Total: 6)
const count = wt.rangeCount(0, tokenStream.length - 1, 10, 40);
console.log('✓ Test 3: Range count in [10..40] across tokenStream: ' + count + ' (expected: 6)');
if (count !== 6) {
  throw new Error('Range count query failed: expected 6, got ' + count);
}

// Test 4: Write verification report
const report = {
  experiment: 'wavelet_tree_quantile',
  phase: 465,
  timestamp: new Date().toISOString(),
  sequenceLength: tokenStream.length,
  alphabetMax: 100,
  minFound: minVal,
  maxFound: maxVal,
  medianFound: medianVal,
  subrangeTest: { range: [2, 7], k0: subK0, k2: subK2, k5: subK5 },
  rangeCountTest: { valRange: [10, 40], occurrences: count },
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_WAVELET_TREE_QUANTILE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_WAVELET_TREE_QUANTILE_REPORT.json');

console.log('All Wavelet Tree Quantile Filter tests passed successfully!');
