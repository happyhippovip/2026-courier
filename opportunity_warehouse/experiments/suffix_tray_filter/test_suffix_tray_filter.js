const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { SuffixTrayFilter } = require('./lib/suffix_tray_filter');

console.log('Testing Suffix Tray Filter...');

const text = 'antigravity_gravity_hotstuff_antigravity_symphony';
const tray = new SuffixTrayFilter(text, 2);

// Test 1: Substring containment and location
assert.strictEqual(tray.count('antigravity'), 2);
assert.deepStrictEqual(tray.locate('antigravity'), [0, 29]);

assert.strictEqual(tray.count('gravity'), 3);
assert.deepStrictEqual(tray.locate('gravity'), [4, 12, 33]);

assert.strictEqual(tray.count('hotstuff'), 1);
assert.deepStrictEqual(tray.locate('hotstuff'), [20]);
console.log('✓ Test 1: Exact substring containment and multi-occurrence locations verified');

// Test 2: Sub-depth query (length < prefixDepth)
const singleCharMatches = tray.locate('a');
assert.strictEqual(singleCharMatches.length, 5); // index 0, 6, 14, 29, 35
console.log('✓ Test 2: Sub-depth single character query verified (matched 5 occurrences)');

// Test 3: Non-existent pattern
assert.strictEqual(tray.contains('non_existent_token'), false);
assert.strictEqual(tray.count('non_existent_token'), 0);
assert.deepStrictEqual(tray.locate('non_existent_token'), []);
console.log('✓ Test 3: Non-existent queries return 0 matches cleanly');

// Test 4: Longest common prefix search
const lcpRes = tray.longestCommonPrefixWithContext('antigravity_agent_core');
assert.strictEqual(lcpRes.prefix, 'antigravity_');
assert.strictEqual(lcpRes.length, 12);
console.log('✓ Test 4: Longest common prefix with context verified ("' + lcpRes.prefix + '", len ' + lcpRes.length + ')');

// Test 5: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_SUFFIX_TRAY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 541,
  metrics: tray.getMetrics(),
  sampleQueries: {
    antigravityLocs: tray.locate('antigravity'),
    gravityLocs: tray.locate('gravity'),
    lcp: lcpRes
  },
  verdict: 'SUFFIX_TRAY_FILTER_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_SUFFIX_TRAY_REPORT.json');

console.log('All Suffix Tray Filter tests passed successfully!');
