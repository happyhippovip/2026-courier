const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { MinHashDeduplicator } = require('../lib/minhash_deduplicator');

const deduplicator = new MinHashDeduplicator({ numHashes: 64, shingleSize: 2, threshold: 0.75 });

// Test 1: Exact duplicate detection yields estimated similarity 1.0
const text1 = 'System verification complete: all 123 tests passed deterministically with zero errors.';
const text2 = 'System verification complete: all 123 tests passed deterministically with zero errors.';
const s1 = deduplicator.createShingles(text1);
const s2 = deduplicator.createShingles(text2);
const sig1 = deduplicator.computeSignature(s1);
const sig2 = deduplicator.computeSignature(s2);
const sim12 = deduplicator.estimateJaccard(sig1, sig2);
assert.strictEqual(sim12, 1.0, 'Identical texts must produce Jaccard similarity 1.0');
console.log('✓ Test 1: Exact duplicate yields 1.0 MinHash similarity');

// Test 2: Near duplicate detection
const textNear = 'System verification complete: all 123 tests passed deterministically with zero errors and warnings.';
const sNear = deduplicator.createShingles(textNear);
const sigNear = deduplicator.computeSignature(sNear);
const simNear = deduplicator.estimateJaccard(sig1, sigNear);
assert.ok(simNear >= 0.70, 'Near duplicate should produce high estimated Jaccard (>= 0.70)');
console.log('✓ Test 2: Near duplicate yields high similarity (' + simNear + ')');

// Test 3: Completely distinct texts yield low similarity
const textDistinct = 'EUR5 commercial customer purchase settlement received via stripe payment gateway.';
const sDistinct = deduplicator.createShingles(textDistinct);
const sigDistinct = deduplicator.computeSignature(sDistinct);
const simDistinct = deduplicator.estimateJaccard(sig1, sigDistinct);
assert.ok(simDistinct < 0.25, 'Distinct texts should have low similarity (< 0.25)');
console.log('✓ Test 3: Distinct texts yield low similarity (' + simDistinct + ')');

// Test 4: Batch deduplication
const batch = [
  { id: 'turn_1', content: 'Agent state initialization: loading configuration parameters and memory buffers.' },
  { id: 'turn_2', content: 'Agent state initialization: loading configuration parameters and memory buffers.' }, // duplicate
  { id: 'turn_3', content: 'Autonomous worker standby cycle: polling customer order mailbox at interval 5000ms.' },
  { id: 'turn_4', content: 'Agent state initialization: loading configuration parameters and local memory buffers.' }, // near-duplicate
  { id: 'turn_5', content: 'Commercial transaction validation: verified €5.00 incoming bank transfer.' }
];

const report = deduplicator.deduplicateBatch(batch, 0.60);
assert.strictEqual(report.retainedCount, 3, 'Should retain exactly 3 unique clusters');
assert.strictEqual(report.duplicateCount, 2, 'Should detect exactly 2 duplicate/near-duplicate items');
assert.ok(report.deduplicationRatio > 0, 'Deduplication ratio should be positive');

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_MINHASH_DEDUPLICATION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Batch deduplication produced expected clusters and wrote evidence');

console.log('All MinHash Deduplicator tests passed successfully!');
