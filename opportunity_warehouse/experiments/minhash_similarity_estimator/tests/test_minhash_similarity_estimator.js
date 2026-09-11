const { MinHashSketch } = require('../lib/minhash_similarity_estimator');
const fs = require('fs');
const path = require('path');

console.log('Testing MinHash Jaccard Similarity Estimator...');
const k = 128;
const sketchA = new MinHashSketch(k);
const sketchB = new MinHashSketch(k);
const sketchC = new MinHashSketch(k);

// Set A: 100 tokens [t_0 .. t_99]
// Set B: 100 tokens [t_50 .. t_149] -> Overlap = 50, Union = 150. True Jaccard = 50 / 150 ≈ 0.333
// Set C: 100 disjoint tokens [t_500 .. t_599] -> True Jaccard with A = 0.00
const tokensA = [];
for (let i = 0; i < 100; i++) tokensA.push('token_' + i);
sketchA.addTokens(tokensA);

const tokensB = [];
for (let i = 50; i < 150; i++) tokensB.push('token_' + i);
sketchB.addTokens(tokensB);

const tokensC = [];
for (let i = 500; i < 600; i++) tokensC.push('token_' + i);
sketchC.addTokens(tokensC);

// Test 1: Identical sets J(A, A) = 1.0
const selfSim = sketchA.estimateJaccard(sketchA);
if (selfSim !== 1.0) throw new Error('Self similarity must be exactly 1.0, got ' + selfSim);
console.log('✓ Test 1: Self similarity J(A, A) = 1.00 verified');

// Test 2: Overlapping sets J(A, B) ≈ 0.333
const estAB = sketchA.estimateJaccard(sketchB);
const diffAB = Math.abs(estAB - (50 / 150));
console.log('✓ Test 2: Estimated J(A, B) = ' + estAB.toFixed(3) + ' (True: 0.333, diff: ' + diffAB.toFixed(3) + ')');
if (diffAB > 0.12) {
  throw new Error('MinHash estimate out of tolerance: ' + estAB);
}

// Test 3: Disjoint sets J(A, C) ≈ 0.0
const estAC = sketchA.estimateJaccard(sketchC);
console.log('✓ Test 3: Estimated J(A, C) = ' + estAC.toFixed(3) + ' (Disjoint test)');
if (estAC > 0.05) {
  throw new Error('Disjoint similarity should be near 0, got ' + estAC);
}

// Test 4: Write verification report
const report = {
  experiment: 'minhash_similarity_estimator',
  phase: 429,
  timestamp: new Date().toISOString(),
  dimensionK: k,
  setASize: tokensA.length,
  setBSize: tokensB.length,
  estimatedJaccardAB: estAB,
  trueJaccardAB: 50 / 150,
  estimatedJaccardAC: estAC,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_MINHASH_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_MINHASH_REPORT.json');

console.log('All MinHash Similarity tests passed successfully!');
