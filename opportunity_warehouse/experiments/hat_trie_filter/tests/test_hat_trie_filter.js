const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { HATTrieFilter } = require('../lib/hat_trie_filter');

console.log('Testing HAT-Trie Cache Filter...');

const filter = new HATTrieFilter(3);

// Test 1: Leaf bucket insertions under capacity
filter.insert('token_alpha', { rank: 1 });
filter.insert('token_beta', { rank: 2 });
assert.strictEqual(filter.burstCount, 0);
assert.deepStrictEqual(filter.search('token_alpha'), { rank: 1 });
assert.deepStrictEqual(filter.search('token_beta'), { rank: 2 });
console.log('✓ Test 1: Keys stored cleanly in hash leaf bucket prior to burst');

// Test 2: Trigger burst upon capacity overflow
filter.insert('token_gamma', { rank: 3 });
filter.insert('token_delta', { rank: 4 }); // 4th item bursts
assert(filter.burstCount >= 1, 'Burst count should increment');
console.log('✓ Test 2: Capacity overflow burst bucket into access trie nodes (bursts: ' + filter.burstCount + ')');

// Test 3: Retrieval after burst
assert.deepStrictEqual(filter.search('token_alpha'), { rank: 1 });
assert.deepStrictEqual(filter.search('token_beta'), { rank: 2 });
assert.deepStrictEqual(filter.search('token_gamma'), { rank: 3 });
assert.deepStrictEqual(filter.search('token_delta'), { rank: 4 });
assert.strictEqual(filter.search('token_nonexistent'), null);
console.log('✓ Test 3: Key retrieval exact across post-burst hash buckets');

// Test 4: Evidence report export
const evidenceReport = {
  experiment: 'hat_trie_filter',
  timestamp: new Date().toISOString(),
  metrics: filter.getMetrics(),
  testKeys: ['token_alpha', 'token_beta', 'token_gamma', 'token_delta'],
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_HAT_TRIE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_HAT_TRIE_REPORT.json');

console.log('All HAT-Trie Filter tests passed successfully!');
