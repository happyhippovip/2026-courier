const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { DoubleArrayTrieFilter } = require('../lib/double_array_trie_filter');

console.log('Testing Double-Array Trie Filter...');

const dat = new DoubleArrayTrieFilter(128);

// Test 1: Insert and Exact O(1) Search
dat.insert('agent', { role: 'COORDINATOR' });
dat.insert('age', { role: 'METRIC' });
assert.deepStrictEqual(dat.search('agent'), { role: 'COORDINATOR' });
assert.deepStrictEqual(dat.search('age'), { role: 'METRIC' });
console.log('✓ Test 1: Exact state transitions and prefix keys verified');

// Test 2: Multiple insertions with shared branches
dat.insert('action', { role: 'EXECUTOR' });
dat.insert('actor', { role: 'PARTICIPANT' });
assert.deepStrictEqual(dat.search('action'), { role: 'EXECUTOR' });
assert.deepStrictEqual(dat.search('actor'), { role: 'PARTICIPANT' });
assert.deepStrictEqual(dat.search('agent'), { role: 'COORDINATOR' });
console.log('✓ Test 2: Multi-key insertion with branch sharing verified');

// Test 3: Missing key lookup
assert.strictEqual(dat.search('unknown'), null);
assert.strictEqual(dat.search('act'), null);
console.log('✓ Test 3: Missing keys return null without traversal error');

// Test 4: Evidence Report Export
const evidenceReport = {
  experiment: 'double_array_trie_filter',
  timestamp: new Date().toISOString(),
  metrics: dat.getMetrics(),
  testKeys: ['agent', 'age', 'action', 'actor'],
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_DOUBLE_ARRAY_TRIE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_DOUBLE_ARRAY_TRIE_REPORT.json');

console.log('All Double-Array Trie Filter tests passed successfully!');
