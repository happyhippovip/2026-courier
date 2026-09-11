const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { EmbeddingAnnealer } = require('../lib/annealer');

const annealer = new EmbeddingAnnealer({ redundancyThreshold: 0.85 });

// Test 1: Quantization and cosine similarity
const rawVec1 = [0.1, 0.5, 0.8, -0.2];
const rawVec2 = [0.1, 0.5, 0.8, -0.2]; // identical
const rawVec3 = [-0.8, -0.2, 0.1, 0.9]; // highly divergent

const q1 = annealer.quantizeToInt8(rawVec1);
const q2 = annealer.quantizeToInt8(rawVec2);
const q3 = annealer.quantizeToInt8(rawVec3);

const sim12 = annealer.cosineSimilarity(q1, q2);
const sim13 = annealer.cosineSimilarity(q1, q3);

assert.strictEqual(sim12, 1.0, 'Identical quantized vectors must have cosine similarity 1.0');
assert.ok(sim13 < 0.2, 'Divergent vectors must have low similarity');
console.log('✓ Test 1: Int8 quantization & cosine similarity verified (' + sim12 + ' vs ' + sim13 + ')');

// Test 2: Prune redundant near-duplicate chunks
const chunks = [
  { id: 'chunk_1', text: 'System initialized core memory', embedding: q1 },
  { id: 'chunk_2', text: 'System initialized core memory buffer', embedding: q2 }, // duplicate
  { id: 'chunk_3', text: 'Financial transaction settlement record', embedding: q3 }
];

const pruneReport = annealer.pruneRedundant(chunks, 0.85);
assert.strictEqual(pruneReport.retainedCount, 2, 'Should retain exactly 2 diverse chunks');
assert.strictEqual(pruneReport.prunedCount, 1, 'Should prune 1 redundant chunk');
assert.strictEqual(pruneReport.pruned[0].id, 'chunk_2');
console.log('✓ Test 2: Redundant chunk pruned, retaining 2 diverse chunks');

// Test 3: Maximal Marginal Relevance selection
const query = annealer.quantizeToInt8([0.15, 0.55, 0.75, -0.15]); // close to q1
const mmrResult = annealer.maximalMarginalRelevance(query, chunks, 2, 0.6);
assert.strictEqual(mmrResult.length, 2, 'Should pick top 2 diverse chunks');
assert.strictEqual(mmrResult[0].id, 'chunk_1', 'chunk_1 should be first due to high relevance');
console.log('✓ Test 3: MMR selected top diverse chunks (' + mmrResult.map(m => m.id).join(', ') + ')');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_EMBEDDING_ANNEALER_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  pruneReport,
  mmrResult,
  quantizationMetrics: {
    scale: q1.scale,
    int8Length: q1.quantized.length
  }
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_EMBEDDING_ANNEALER_REPORT.json');

console.log('All Embedding Annealer tests passed successfully!');
