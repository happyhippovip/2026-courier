const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CuckooFilter } = require('./lib/cuckoo_filter');

console.log('Testing Cuckoo Filter & Dynamic Deletion...');

const filter = new CuckooFilter(128, 4);

const sampleTokens = ['symphony', 'autonomous', 'revenue', 'optimizer', 'context', 'trimmer'];
for (const t of sampleTokens) {
  const ok = filter.insert(t);
  assert.strictEqual(ok, true);
}

// Test 1: Exact positive lookup
for (const t of sampleTokens) {
  assert.strictEqual(filter.has(t), true);
}
console.log('✓ Test 1: Exact lookup verified for all 6 inserted tokens');

// Test 2: Dynamic deletion
const deleted = filter.delete('optimizer');
assert.strictEqual(deleted, true);
assert.strictEqual(filter.has('optimizer'), false);
assert.strictEqual(filter.has('symphony'), true); // Others remain untouched
console.log('✓ Test 2: Dynamic deletion verified without filter rebuild');

// Test 3: Re-insert after deletion
const reinserted = filter.insert('optimizer');
assert.strictEqual(reinserted, true);
assert.strictEqual(filter.has('optimizer'), true);
console.log('✓ Test 3: Re-insertion after deletion successful');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 353,
  component: 'cuckoo_filter',
  bucketCount: 128,
  bucketCapacity: 4,
  tokensContained: filter.count,
  dynamicDeletionVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_CUCKOO_FILTER_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_CUCKOO_FILTER_REPORT.json');
console.log('All Cuckoo Filter tests passed successfully!');
