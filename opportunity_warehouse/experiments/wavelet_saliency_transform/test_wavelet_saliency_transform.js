const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { WaveletSaliencyTransform } = require('./lib/wavelet_saliency_transform');

console.log('Testing Wavelet Saliency Transform...');

const rawSaliency = [0.1, 0.12, 0.85, 0.88, 0.4, 0.42, 0.95, 0.96];

// Test 1: Forward and exact inverse reconstruction
const tf = WaveletSaliencyTransform.forward(rawSaliency);
assert.strictEqual(tf.approx.length, 4);
assert.strictEqual(tf.detail.length, 4);

const rec = WaveletSaliencyTransform.inverse(tf.approx, tf.detail, rawSaliency.length);
for (let i = 0; i < rawSaliency.length; i++) {
  assert.ok(Math.abs(rec[i] - rawSaliency[i]) < 1e-6);
}
console.log('✓ Test 1: Exact Haar wavelet lossless roundtrip verified');

// Test 2: Threshold compression
const comp = WaveletSaliencyTransform.compress(rawSaliency, 0.05);
assert.ok(comp.sparsityRatio > 0.2); // Saliency pairs are close, so detail is small and pruned
console.log('✓ Test 2: Saliency sparsity pruning verified (' + (comp.sparsityRatio * 100).toFixed(1) + '% details zeroed)');

// Test 3: Macro trend preservation
// High saliency cluster around indices 2,3 and 6,7 remains prominent
assert.ok(comp.reconstructed[2] > 0.7);
assert.ok(comp.reconstructed[6] > 0.8);
console.log('✓ Test 3: Macro saliency peaks preserved post-compression');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 325,
  component: 'wavelet_saliency_transform',
  inputLength: rawSaliency.length,
  sparsityAchieved: comp.sparsityRatio,
  reconstructionErrorMax: Math.max(...rawSaliency.map((val, idx) => Math.abs(val - comp.reconstructed[idx]))),
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_WAVELET_SALIENCY_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_WAVELET_SALIENCY_REPORT.json');
console.log('All Wavelet Saliency Transform tests passed successfully!');
