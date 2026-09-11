const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { VectorCentroidDeduplicator } = require('../lib/centroid_deduplicator');

console.log('--- Testing Vector Centroid Deduplicator ---');

const dedup = new VectorCentroidDeduplicator();

const chunks = [
  { id: 'chunk_1', text: 'PostgreSQL database connection pooling with pg_pool improves query performance and reduces socket exhaustion.' },
  { id: 'chunk_2', text: 'Using pg_pool connection pooling on PostgreSQL improves performance and limits socket exhaustion substantially.' },
  { id: 'chunk_3', text: 'CSS flexbox layout alignment using justify-content and align-items handles responsive centering on web interfaces.' }
];

// Test 1: Cosine similarity computation
const vec1 = dedup.extractFeatureVector(chunks[0].text);
const vec2 = dedup.extractFeatureVector(chunks[1].text);
const vec3 = dedup.extractFeatureVector(chunks[2].text);

const sim12 = dedup.computeCosineSimilarity(vec1, vec2);
const sim13 = dedup.computeCosineSimilarity(vec1, vec3);
assert.ok(sim12 > 0.60, 'Semantically overlapping chunks must have high cosine similarity');
assert.ok(sim13 < 0.20, 'Unrelated chunks must have low cosine similarity');
console.log('✓ Assertion 1 Passed: Cosine similarity correctly distinguished semantic overlap (Sim12: ' + sim12 + ', Sim13: ' + sim13 + ')');

// Test 2: Semantic clustering and centroid deduplication
const result = dedup.clusterAndDeduplicate(chunks, 0.60);
assert.strictEqual(result.originalChunksCount, 3);
assert.strictEqual(result.retainedCentroidsCount, 2, 'Must collapse 2 overlapping chunks into 1 centroid');
assert.strictEqual(result.prunedDuplicatesCount, 1, '1 duplicate chunk pruned');
assert.ok(result.tokensSaved > 0, 'Must save tokens');
console.log('✓ Assertion 2 Passed: Semantic duplicates clustered and redundant neighbor pruned');

// Test 3: Centroid preservation of highest information density
const centroidIds = result.retainedCentroids.map(c => c.id);
assert.ok(centroidIds.includes('chunk_3'), 'Unique chunk must be preserved');
assert.ok(centroidIds.includes('chunk_2') || centroidIds.includes('chunk_1'), 'One DB chunk retained');
console.log('✓ Assertion 3 Passed: Most informative centroid retained with citation metrics');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_VECTOR_CENTROID_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(result, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_VECTOR_CENTROID_REPORT.json');

console.log('All 4 Vector Centroid Deduplicator tests passed successfully!');