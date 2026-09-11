const { WaveletMatrixTopK } = require('../lib/wavelet_matrix_topk');
const fs = require('fs');
const path = require('path');

console.log('Testing Wavelet Matrix Top-K Heavy Saliency Filter...');

// Token sequence: 20 saliency scores in [0 .. 127]
const saliencies = [15, 92, 45, 120, 8, 92, 110, 33, 76, 120, 5, 88, 110, 14, 99, 120, 50, 62, 92, 105];
const wmtk = new WaveletMatrixTopK(saliencies, 127);

// Test 1: Extract Top-3 highest values in the full array [0 .. 19]
// Expected: 120 (count 3), 110 (count 2), 105 (count 1)
const top3 = wmtk.getTopK(0, saliencies.length - 1, 3);
console.log('✓ Test 1: Top-3 saliencies extracted: ' + JSON.stringify(top3));

if (top3.length < 3 || top3[0].value !== 120 || top3[0].count !== 3 || top3[1].value !== 110 || top3[2].value !== 105) {
  throw new Error('Top-3 extraction on full array failed');
}

// Test 2: Subrange Top-2 query in [4 .. 13]
// Subrange: [8, 92, 110, 33, 76, 120, 5, 88, 110, 14]
// Top values: 120 (count 1), 110 (count 2), 92 (count 1)
const subTop2 = wmtk.getTopK(4, 13, 2);
console.log('✓ Test 2: Subrange [4..13] Top-2 saliencies: ' + JSON.stringify(subTop2));
if (subTop2.length < 2 || subTop2[0].value !== 120 || subTop2[1].value !== 110) {
  throw new Error('Subrange Top-2 extraction failed');
}

// Test 3: Verify sorting correctness
for (let i = 0; i < top3.length - 1; i++) {
  if (top3[i].value < top3[i + 1].value) {
    throw new Error('Top-K ordering invariant violated');
  }
}
console.log('✓ Test 3: Monotonic descending ordering invariant verified');

// Test 4: Write verification report
const report = {
  experiment: 'wavelet_matrix_topk',
  phase: 473,
  timestamp: new Date().toISOString(),
  sequenceLength: saliencies.length,
  alphabetMax: 127,
  fullRangeTop3: top3,
  subrangeTop2: subTop2,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_WAVELET_MATRIX_TOPK_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_WAVELET_MATRIX_TOPK_REPORT.json');

console.log('All Wavelet Matrix Top-K tests passed successfully!');
