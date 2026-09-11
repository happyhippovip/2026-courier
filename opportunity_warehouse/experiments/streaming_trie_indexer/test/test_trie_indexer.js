const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { StreamingTrieIndexer } = require('../lib/trie_indexer');

const indexer = new StreamingTrieIndexer();

// Test 1: Insert and search exact symbol match
indexer.insert('AgentScheduler', { type: 'class', module: 'core/scheduler' });
indexer.insert('AgentScheduler', { type: 'class', module: 'core/scheduler' });
const searchResult = indexer.search('AgentScheduler');
assert.ok(searchResult !== null, 'Symbol must exist in trie');
assert.strictEqual(searchResult.frequency, 2, 'Frequency must be 2');
assert.strictEqual(searchResult.metadata.type, 'class');
console.log('✓ Assertion 1 Passed: Exact symbol search returned node with frequency 2');

// Test 2: Prefix lookup finds all candidate completions sorted by frequency
indexer.insert('agentWorker', { type: 'worker' });
indexer.insert('agentDispatcher', { type: 'dispatcher' });
indexer.insert('agentWorker', { type: 'worker' });
indexer.insert('agentWorker', { type: 'worker' });
const prefixMatches = indexer.findWithPrefix('agent');
assert.strictEqual(prefixMatches.length, 3, 'Must match AgentScheduler, agentWorker, agentDispatcher');
assert.strictEqual(prefixMatches[0].word, 'agentworker', 'Most frequent completion must be first');
assert.strictEqual(prefixMatches[0].frequency, 3);
console.log('✓ Assertion 2 Passed: Prefix search ranked completions by frequency correctly');

// Test 3: Incremental streaming chunk ingestion
const streamChunk = 'Incoming webhook receipt from payment_gateway with status SETTLED for order_49102.';
const res = indexer.indexStreamChunk(streamChunk, { source: 'stream_turn_5' });
assert.ok(res.indexedTokenCount > 0, 'Must index tokens from stream chunk');
const orderLookup = indexer.search('order_49102');
assert.ok(orderLookup !== null, 'order_49102 must be indexed');
assert.strictEqual(orderLookup.metadata.source, 'stream_turn_5');
console.log('✓ Assertion 3 Passed: Streaming chunk indexed incrementally without index resets');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_STREAMING_TRIE_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  totalWordsIndexed: indexer.totalWordsIndexed,
  prefixMatchesForAgent: prefixMatches,
  exactSearchVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_STREAMING_TRIE_REPORT.json');

console.log('All 4 Streaming Trie Indexer tests passed successfully!');