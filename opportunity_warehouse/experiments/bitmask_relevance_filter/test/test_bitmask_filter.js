const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BitmaskRelevanceFilter } = require('../lib/bitmask_filter');

const filter = new BitmaskRelevanceFilter(['system', 'user', 'tool', 'settlement', 'urgent', 'deprecated']);

// Test 1: Bitmask creation and tag registration
const m1 = filter.computeMask(['system', 'urgent']);
const m2 = filter.computeMask(['tool', 'settlement']);
assert.strictEqual(typeof m1, 'bigint', 'Mask must be BigInt');
assert.strictEqual(m1 & m2, 0n, 'Disjoint tags must produce zero intersection');
console.log('✓ Test 1: BigInt bitmask computation verified');

// Test 2: Compound query evaluation (requireAll, requireAny, exclude)
filter.addItem('c1', 'System prompt initialization', ['system', 'urgent']);
filter.addItem('c2', 'Tool invocation: execute order settlement', ['tool', 'settlement', 'urgent']);
filter.addItem('c3', 'Deprecated customer note', ['user', 'deprecated']);
filter.addItem('c4', 'Tool invocation: read file', ['tool']);

// Query: urgent items that are NOT deprecated
const q1 = filter.filter({ requireAll: ['urgent'], exclude: ['deprecated'] });
assert.strictEqual(q1.matchedCount, 2, 'Should match exactly c1 and c2');
assert.strictEqual(q1.matched[0].id, 'c1');
assert.strictEqual(q1.matched[1].id, 'c2');
console.log('✓ Test 2: Accurate compound filtering (requireAll + exclude)');

// Test 3: RequireAny filtering
const q2 = filter.filter({ requireAny: ['system', 'tool'] });
assert.strictEqual(q2.matchedCount, 3, 'Should match c1, c2, c4');
console.log('✓ Test 3: Accurate requireAny filtering');

// Test 4: Performance evaluation over 500 items and evidence write
for (let i = 0; i < 500; i++) {
  filter.addItem('bulk_' + i, 'Bulk context chunk #' + i, (i % 2 === 0) ? ['tool'] : ['user']);
}

const perf = filter.batchFilterPerformance({ requireAll: ['tool'], exclude: ['deprecated'] }, 500);
assert.ok(perf.avgMicrosecondsPerQuery < 500, 'Filtering 500 items should take under 500 microseconds');

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_BITMASK_FILTER_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  performance: perf,
  sampleMatches: q1.matched.map(m => ({ id: m.id, tags: m.tags })),
  registeredTagsCount: filter.tagMap.size
}, null, 2), 'utf8');
console.log('✓ Test 4: High performance confirmed (' + perf.avgMicrosecondsPerQuery + ' µs/query) and evidence written');

console.log('All Bitmask Relevance Filter tests passed successfully!');
