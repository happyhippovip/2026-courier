const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixTreeInvertedMapFilter } = require('../lib/radix_tree_inverted_map_filter');

console.log('Testing Radix Tree Inverted Token Map Filter...');

const rtm = new RadixTreeInvertedMapFilter();

// Test 1: Ingest documents
rtm.insert('agent', 'doc_1');
rtm.insert('loop', 'doc_1');
rtm.insert('detect', 'doc_1');

rtm.insert('agent', 'doc_2');
rtm.insert('verify', 'doc_2');
rtm.insert('gate', 'doc_2');

rtm.insert('loop', 'doc_3');
rtm.insert('gate', 'doc_3');

// Test 2: Exact search and posting retrieval
const agentPostings = rtm.search('agent');
assert.strictEqual(agentPostings.length, 2);
assert.deepStrictEqual(agentPostings.map(p => p.docId).sort(), ['doc_1', 'doc_2']);
console.log('✓ Test 1: Single token posting lists retrieved via compressed radix edges');

// Test 3: Boolean intersection AND query
const andRes = rtm.queryAND(['agent', 'loop']);
assert.deepStrictEqual(andRes, ['doc_1'], 'Only doc_1 contains both agent and loop');
console.log('✓ Test 2: Boolean AND intersection correctly localized document:', andRes);

const andResGate = rtm.queryAND(['agent', 'gate']);
assert.deepStrictEqual(andResGate, ['doc_2']);
console.log('✓ Test 3: Multiple AND intersections accurately resolved across documents');

// Test 4: Missing token query returns empty
assert.deepStrictEqual(rtm.search('nonexistent'), []);
assert.deepStrictEqual(rtm.queryAND(['agent', 'nonexistent']), []);
console.log('✓ Test 4: Missing tokens return empty posting lists gracefully');

// Test 5: Export evidence report
const evidenceReport = {
  experiment: 'radix_tree_inverted_map_filter',
  timestamp: new Date().toISOString(),
  testQueries: [
    { word: 'agent', postings: agentPostings },
    { andQuery: ['agent', 'loop'], result: andRes }
  ],
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_INVERTED_MAP_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 5: Evidence report written to SAMPLE_RADIX_INVERTED_MAP_REPORT.json');

console.log('All Radix Tree Inverted Token Map Filter tests passed successfully!');
