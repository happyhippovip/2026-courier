const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TrieInvertedIndex } = require('./lib/trie_inverted_index');

console.log('Testing Hierarchical Trie-Based Inverted Index...');

const index = new TrieInvertedIndex();

const doc1 = ['the', 'autonomous', 'agent', 'executes', 'symphony', 'workflow'];
const doc2 = ['symphony', 'is', 'an', 'autonomous', 'orchestration', 'agent'];
const doc3 = ['unrelated', 'weather', 'forecast', 'report'];

index.indexDocument('doc-1', doc1);
index.indexDocument('doc-2', doc2);
index.indexDocument('doc-3', doc3);

// Test 1: Single token posting retrieval
const agentPostings = index.getPostings('agent');
assert.ok(agentPostings !== null);
assert.deepStrictEqual(agentPostings.get('doc-1'), [2]);
assert.deepStrictEqual(agentPostings.get('doc-2'), [5]);
assert.strictEqual(agentPostings.has('doc-3'), false);
console.log('✓ Test 1: Single token posting retrieval verified');

// Test 2: Proximity search within maxDistance = 3
const proximity = index.searchProximity('autonomous', 'agent', 3);
assert.strictEqual(proximity.length, 2);
assert.strictEqual(proximity[0].docId, 'doc-1');
assert.strictEqual(proximity[0].minDistance, 1);
assert.strictEqual(proximity[1].docId, 'doc-2');
assert.strictEqual(proximity[1].minDistance, 2);
console.log('✓ Test 2: Proximity search with positional distance ranking verified');

// Test 3: Unmatched search
const noMatch = index.searchProximity('weather', 'symphony', 2);
assert.strictEqual(noMatch.length, 0);
console.log('✓ Test 3: Non-matching pair returns empty result');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 299,
  component: 'trie_inverted_index',
  indexedDocuments: 3,
  query: { termA: 'autonomous', termB: 'agent', maxDistance: 3 },
  results: proximity,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_TRIE_INVERTED_INDEX_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_TRIE_INVERTED_INDEX_REPORT.json');
console.log('All Trie Inverted Index tests passed successfully!');
