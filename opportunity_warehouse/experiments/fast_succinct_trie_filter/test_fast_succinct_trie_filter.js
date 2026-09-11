const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { FastSuccinctTrieBuilder } = require('./lib/fast_succinct_trie_filter');

console.log('Testing Fast Succinct Trie (FST) Filter...');

const builder = new FastSuccinctTrieBuilder();
const testKeys = [
  'antigravity',
  'agent',
  'algorithm',
  'aleph',
  'aleph_consensus',
  'hotstuff',
  'hotstuff_engine',
  'pipelined',
  'p0_revenue',
  'symphony'
];

testKeys.forEach(k => builder.insert(k, { tokenRef: 'ref_' + k, length: k.length }));

const trie = builder.build();

// Test 1: Exact matches for all inserted keys
testKeys.forEach(k => {
  const res = trie.exactMatch(k);
  assert.strictEqual(res.found, true, 'Key ' + k + ' must be found');
  assert.strictEqual(res.value.tokenRef, 'ref_' + k, 'Value must match');
});
console.log('✓ Test 1: Exact matches verified across all keys');

// Test 2: Non-existent keys and prefix checks
const nonKeys = ['ant', 'ale', 'hot', 'random_missing_token', 'agentic'];
nonKeys.forEach(nk => {
  const res = trie.exactMatch(nk);
  assert.strictEqual(res.found, false, 'Non-inserted key ' + nk + ' must not be terminal');
});
assert.strictEqual(trie.hasPrefix('anti'), true, 'Prefix anti must exist');
assert.strictEqual(trie.hasPrefix('aleph_'), true, 'Prefix aleph_ must exist');
assert.strictEqual(trie.hasPrefix('xyz'), false, 'Prefix xyz must not exist');
console.log('✓ Test 2: Prefix detection and non-terminal handling verified');

// Test 3: Longest Prefix Match
const lpm1 = trie.longestPrefixMatch('antigravity_execution_daemon');
assert.strictEqual(lpm1.match, 'antigravity');
assert.strictEqual(lpm1.length, 11);

const lpm2 = trie.longestPrefixMatch('aleph_consensus_round_12');
assert.strictEqual(lpm2.match, 'aleph_consensus');
assert.strictEqual(lpm2.length, 15);

const lpm3 = trie.longestPrefixMatch('unknown_prefix_data');
assert.strictEqual(lpm3.match, null);
console.log('✓ Test 3: Longest prefix matching verified on compound query text');

// Test 4: Succinct compression metrics
const metrics = trie.getMetrics();
assert(metrics.succinctBytes < metrics.pointerTrieEstimatedBytes, 'Succinct representation must save space');
assert(metrics.compressionRatio > 0.5, 'Compression savings must exceed 50%');
console.log('✓ Test 4: Succinct compression verified (Savings: ' + metrics.savingsPercent + ', ' + metrics.succinctBytes + ' bytes vs ' + metrics.pointerTrieEstimatedBytes + ' bytes)');

// Test 5: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_FAST_SUCCINCT_TRIE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 501,
  metrics,
  sampleQueries: {
    exactMatchAntigravity: trie.exactMatch('antigravity'),
    lpmCompound: lpm1
  },
  verdict: 'FAST_SUCCINCT_TRIE_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_FAST_SUCCINCT_TRIE_REPORT.json');

console.log('All Fast Succinct Trie tests passed successfully!');
