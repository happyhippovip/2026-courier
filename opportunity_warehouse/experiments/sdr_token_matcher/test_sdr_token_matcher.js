const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SDRTokenMatcher } = require('./lib/sdr_token_matcher');

console.log('Testing SDR Token Matcher...');

const matcher = new SDRTokenMatcher(1024, 20);

// Test 1: Deterministic encoding with strict w=20 sparsity
const sdrSymphony = matcher.encode('symphony');
assert.strictEqual(sdrSymphony.length, 20);
const ratio = matcher.overlapRatio(sdrSymphony, sdrSymphony);
assert.strictEqual(ratio, 1.0);
console.log('✓ Test 1: Deterministic SDR encoded with exact 20 active bits (100% self-overlap)');

// Test 2: Noise tolerance under 15% bit corruption (3 flipped bits)
const noisySymphony = matcher.corrupt(sdrSymphony, 3);
const noiseOverlap = matcher.overlapRatio(sdrSymphony, noisySymphony);
assert.strictEqual(noiseOverlap, 17 / 20); // 85% overlap retained!
assert.ok(noiseOverlap >= 0.80);
console.log('✓ Test 2: High noise tolerance verified: 85% overlap preserved under 3 flipped bits');

// Test 3: Orthogonality between unrelated concepts
const sdrBanana = matcher.encode('banana');
const orthogonalOverlap = matcher.overlapRatio(sdrSymphony, sdrBanana);
assert.ok(orthogonalOverlap <= 0.10); // Less than 10% overlap
console.log('✓ Test 3: Orthogonality verified between distinct concepts (overlap: ' + (orthogonalOverlap * 100).toFixed(1) + '%)');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 373,
  component: 'sdr_token_matcher',
  nVectorDimension: 1024,
  wActiveBits: 20,
  noiseToleranceRatio: noiseOverlap,
  orthogonalOverlapRatio: orthogonalOverlap,
  sparseDistributedInvariantsVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_SDR_MATCHER_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_SDR_MATCHER_REPORT.json');
console.log('All SDR Token Matcher tests passed successfully!');
