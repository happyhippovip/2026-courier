const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BurstTrieFilter } = require('../lib/burst_trie_filter');

console.log('Testing Burst Trie Filter...');

const trie = new BurstTrieFilter(3);

// Test 1: Insert below burst threshold
trie.insert('apple', { id: 1 });
trie.insert('apply', { id: 2 });
assert.strictEqual(trie.burstCount, 0);
assert.deepStrictEqual(trie.search('apple'), { id: 1 });
assert.deepStrictEqual(trie.search('apply'), { id: 2 });
console.log('✓ Test 1: Insertions below threshold remain in compact leaf container');

// Test 2: Triggering burst upon threshold overflow
trie.insert('app', { id: 3 });
trie.insert('apricot', { id: 4 }); // 4th item triggers burst
assert(trie.burstCount >= 1, 'Burst count should increase upon overflow');
console.log('✓ Test 2: Capacity overflow triggered automatic node burst (bursts: ' + trie.burstCount + ')');

// Test 3: Lookups across burst nodes
assert.deepStrictEqual(trie.search('apple'), { id: 1 });
assert.deepStrictEqual(trie.search('apply'), { id: 2 });
assert.deepStrictEqual(trie.search('app'), { id: 3 });
assert.deepStrictEqual(trie.search('apricot'), { id: 4 });
assert.strictEqual(trie.search('nonexistent'), null);
console.log('✓ Test 3: Correct retrieval verified for all keys after bursting');

// Test 4: Evidence report export
const evidenceReport = {
  experiment: 'burst_trie_filter',
  timestamp: new Date().toISOString(),
  metrics: trie.getMetrics(),
  testKeys: ['apple', 'apply', 'app', 'apricot'],
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_BURST_TRIE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_BURST_TRIE_REPORT.json');

console.log('All Burst Trie Filter tests passed successfully!');
