const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { HierarchicalBloomFilter } = require('./lib/hierarchical_bloom_filter');

console.log('Testing Hierarchical Bloom Filter...');

const filter = new HierarchicalBloomFilter();

const tokens = ['symphony', 'autonomous', 'revenue', 'agent', 'context', 'trimmer'];
for (const t of tokens) {
  filter.add(t);
}

// Test 1: Zero false negatives for present keys
for (const t of tokens) {
  assert.strictEqual(filter.mightContain(t), true);
}
console.log('✓ Test 1: Zero false negatives verified across all inserted tokens');

// Test 2: Negative rejection for non-present keys
const unseen = ['banana', 'elephant', 'xylophone', 'quasar', 'submarine'];
for (const u of unseen) {
  assert.strictEqual(filter.mightContain(u), false);
}
console.log('✓ Test 2: Unseen keys rejected by fast negative filter');

// Test 3: False positive rate bounded < 2%
let falsePositives = 0;
const testCount = 1000;
for (let i = 0; i < testCount; i++) {
  const randomKey = 'rand_key_' + Math.random().toString(36).substring(2);
  if (filter.mightContain(randomKey)) {
    falsePositives++;
  }
}
const fpr = falsePositives / testCount;
assert.ok(fpr < 0.02);
console.log('✓ Test 3: Empirical false positive rate verified: ' + (fpr * 100).toFixed(2) + '% (< 2%)');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 329,
  component: 'hierarchical_bloom_filter',
  insertedTokensCount: tokens.length,
  testNegativeQueries: testCount,
  falsePositiveRate: fpr,
  zeroFalseNegatives: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_HIERARCHICAL_BLOOM_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_HIERARCHICAL_BLOOM_REPORT.json');
console.log('All Hierarchical Bloom Filter tests passed successfully!');
