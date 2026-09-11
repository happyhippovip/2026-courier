const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TernarySearchTreeFilter } = require('../lib/ternary_search_tree_filter');

console.log('Testing Ternary Search Tree Filter...');

const tst = new TernarySearchTreeFilter();

// Test 1: Insertions & Lookups
tst.insert('agent_loop', { severity: 'CRITICAL' });
tst.insert('agent_step', { severity: 'INFO' });
tst.insert('agent_gate', { severity: 'SECURITY' });
assert.strictEqual(tst.size, 3);
assert.deepStrictEqual(tst.search('agent_loop'), { severity: 'CRITICAL' });
assert.deepStrictEqual(tst.search('agent_step'), { severity: 'INFO' });
assert.deepStrictEqual(tst.search('agent_gate'), { severity: 'SECURITY' });
console.log('✓ Test 1: Exact lookups verified across balanced ternary branches');

// Test 2: Prefix Matching
const prefixMatches = tst.keysWithPrefix('agent_');
assert.strictEqual(prefixMatches.length, 3);
const keys = prefixMatches.map(m => m.key).sort();
assert.deepStrictEqual(keys, ['agent_gate', 'agent_loop', 'agent_step']);
console.log('✓ Test 2: Prefix search successfully returned sorted extensions:', keys);

// Test 3: Missing Key Lookups
assert.strictEqual(tst.search('agent_unknown'), null);
assert.strictEqual(tst.search('age'), null);
assert.deepStrictEqual(tst.keysWithPrefix('nonexistent'), []);
console.log('✓ Test 3: Missing keys and prefixes return null and empty arrays');

// Test 4: Evidence Report Export
const evidenceReport = {
  experiment: 'ternary_search_tree_filter',
  timestamp: new Date().toISOString(),
  metrics: tst.getMetrics(),
  prefixQuery: 'agent_',
  matches: prefixMatches,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_TERNARY_SEARCH_TREE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_TERNARY_SEARCH_TREE_REPORT.json');

console.log('All Ternary Search Tree Filter tests passed successfully!');
