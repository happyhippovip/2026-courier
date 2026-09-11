const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { PersistentSuffixTreeFilter } = require('../lib/persistent_suffix_tree_filter');

console.log('Testing Persistent Suffix Tree Filter...');

const filter = new PersistentSuffixTreeFilter();
const tokens = ['agent', 'loop', 'detect', 'pass', 'agent', 'loop', 'detect', 'checkpoint'];
filter.build(tokens);

// Test 1: Substring pattern lookup
const res1 = filter.search(['agent', 'loop']);
assert.strictEqual(res1.found, true, 'Pattern should be found');
assert.strictEqual(res1.occurrences, 2, 'Should occur twice');
assert.deepStrictEqual(res1.indices, [0, 4], 'Indices should be 0 and 4');
console.log('✓ Test 1: Suffix tree pattern lookup verified with multiple occurrences');

// Test 2: Missing pattern lookup
const res2 = filter.search(['unknown', 'token']);
assert.strictEqual(res2.found, false, 'Missing pattern should return false');
assert.strictEqual(res2.occurrences, 0);
console.log('✓ Test 2: Missing pattern correctly returns found=false');

// Test 3: Longest repeated sequence detection
const repeated = filter.findLongestRepeatedSequence(2);
assert.deepStrictEqual(repeated, ['agent', 'loop', 'detect'], 'Longest repeated pattern matches');
console.log('✓ Test 3: Longest repeated sequence detected accurately:', repeated);

// Test 4: Evidence report export
const evidenceReport = {
  experiment: 'persistent_suffix_tree_filter',
  timestamp: new Date().toISOString(),
  tokenCount: tokens.length,
  testQueries: [
    { query: ['agent', 'loop'], result: res1 },
    { query: ['unknown', 'token'], result: res2 }
  ],
  longestRepeatedSequence: repeated,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_PERSISTENT_SUFFIX_TREE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_PERSISTENT_SUFFIX_TREE_REPORT.json');

console.log('All Persistent Suffix Tree Filter tests passed successfully!');
