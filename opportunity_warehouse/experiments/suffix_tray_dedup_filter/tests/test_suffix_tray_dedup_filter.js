const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SuffixTrayDedupFilter } = require('../lib/suffix_tray_dedup_filter');

console.log('Testing Suffix Tray Deduplication Filter...');

const filter = new SuffixTrayDedupFilter(8, 3);

// Test 1: Ingest clean unique sequence
const chunk1 = ['task', 'start', 'execute', 'verify', 'checkpoint'];
const res1 = filter.ingest(chunk1, 'chunk_1');
assert.strictEqual(res1.duplicateHits, 0);
assert.strictEqual(res1.isDuplicateCandidate, false);
console.log('✓ Test 1: Unique chunk ingested without duplicate false alarms');

// Test 2: Ingest identical duplicate sequence
const chunk2 = ['task', 'start', 'execute', 'verify', 'checkpoint'];
const res2 = filter.ingest(chunk2, 'chunk_2');
assert(res2.duplicateHits > 0, 'Duplicate hits must be detected');
assert.strictEqual(res2.isDuplicateCandidate, true);
console.log('✓ Test 2: Identical sequence flagged as duplicate candidate (ratio: ' + res2.duplicateRatio + ')');

// Test 3: Partially overlapping sequence
const chunk3 = ['task', 'start', 'execute', 'NEW_BRANCH', 'STOP'];
const res3 = filter.ingest(chunk3, 'chunk_3');
assert(res3.duplicateHits >= 1);
console.log('✓ Test 3: Sub-sequence overlap accurately detected across trays');

// Test 4: Evidence report export
const evidenceReport = {
  experiment: 'suffix_tray_dedup_filter',
  timestamp: new Date().toISOString(),
  metrics: filter.getMetrics(),
  testResults: [res1, res2, res3],
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SUFFIX_TRAY_DEDUP_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_SUFFIX_TRAY_DEDUP_REPORT.json');

console.log('All Suffix Tray Deduplication Filter tests passed successfully!');
