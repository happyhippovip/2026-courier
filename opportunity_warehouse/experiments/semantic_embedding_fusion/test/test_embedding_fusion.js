const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SemanticEmbeddingFusion } = require('../lib/embedding_fusion');

const engine = new SemanticEmbeddingFusion();

// Projection matrix: maps 4D vector to 3D normalized canonical latent space
const projection4to3 = [
  [0.6, 0.2, 0.1, 0.1],
  [0.1, 0.7, 0.1, 0.1],
  [0.1, 0.1, 0.7, 0.1]
];

const rawVectorA = [1.0, 0.5, 0.1, 0.0];
const rawVectorB = [0.9, 0.6, 0.2, 0.0];
const rawVectorC = [0.0, 0.1, 0.9, 1.0];

// Test 1: Project vector and verify normalization
const projA = engine.projectVector(rawVectorA, projection4to3);
assert.strictEqual(projA.length, 3, 'Projected vector must have dimension 3');
const normA = engine.computeNorm(projA);
assert.ok(Math.abs(normA - 1.0) < 1e-5, 'Projected vector must be unit normalized');
console.log('✓ Assertion 1 Passed: Vector projected to 3D space and unit normalized');

// Test 2: Cosine similarity on projected space distinguishes semantic proximity
const projB = engine.projectVector(rawVectorB, projection4to3);
const projC = engine.projectVector(rawVectorC, projection4to3);
const simAB = engine.computeCosineSimilarity(projA, projB);
const simAC = engine.computeCosineSimilarity(projA, projC);
assert.ok(simAB > 0.85, 'Related vectors must exhibit high similarity in projected space (sim=' + simAB + ')');
assert.ok(simAC < 0.65, 'Divergent vectors must exhibit lower similarity in projected space (sim=' + simAC + ')');
console.log('✓ Assertion 2 Passed: Semantic similarity accurately preserved in projection (AB: ' + simAB + ', AC: ' + simAC + ')');

// Test 3: Weighted embedding fusion produces valid unit centroid
const fused = engine.fuseEmbeddings([
  { vector: projA, weight: 0.7 },
  { vector: projB, weight: 0.3 }
]);
assert.strictEqual(fused.length, 3);
const normFused = engine.computeNorm(fused);
assert.ok(Math.abs(normFused - 1.0) < 1e-5, 'Fused vector must be unit normalized');
const simFusedA = engine.computeCosineSimilarity(fused, projA);
assert.ok(simFusedA > 0.95, 'Fused vector must be tightly aligned with primary contributor');
console.log('✓ Assertion 3 Passed: Weighted fusion generated coherent semantic centroid');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_EMBEDDING_FUSION_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  inputDimension: 4,
  projectedDimension: 3,
  similarityAB: simAB,
  similarityAC: simAC,
  fusedCentroidNorm: normFused,
  alignmentVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_EMBEDDING_FUSION_REPORT.json');

console.log('All 4 Semantic Embedding Fusion tests passed successfully!');