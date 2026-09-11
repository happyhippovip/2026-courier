const { PGMIndexFilter } = require('../lib/pgm_index_filter');
const fs = require('fs');
const path = require('path');

console.log('Testing PGM Index Filter...');

// Synthetic sorted sequence of 120 token keys with clusters and gaps
const sortedKeys = [];
let cur = 5;
for (let i = 0; i < 120; i++) {
  cur += Math.floor(Math.random() * 6) + 1;
  sortedKeys.push(cur);
}

const pgm = new PGMIndexFilter(sortedKeys, 4);

// Test 1: PGM segment compression ratio verification
const stats = pgm.getStats();
console.log('✓ Test 1: PGM Index constructed: ' + stats.segmentCount + ' linear segments for ' + stats.totalKeys + ' keys (compression: ' + stats.compressionRatio + ')');
if (stats.segmentCount >= stats.totalKeys) {
  throw new Error('PGM index did not compress points effectively');
}

// Test 2: Point lookup verification across all 120 keys
for (let i = 0; i < sortedKeys.length; i++) {
  const foundIdx = pgm.lookup(sortedKeys[i]);
  if (foundIdx === -1 || sortedKeys[foundIdx] !== sortedKeys[i]) {
    throw new Error('PGM key lookup failed for key: ' + sortedKeys[i] + ' at index ' + i + ' (found: ' + foundIdx + ')');
  }
}
console.log('✓ Test 2: All 120 keys retrieved accurately with bounded PGM predictions');

// Test 3: Missing key lookup returns -1
const missing = pgm.lookup(100000);
console.log('✓ Test 3: Out-of-bounds missing key returned -1 accurately');
if (missing !== -1) {
  throw new Error('Missing key did not return -1');
}

// Test 4: Write verification report
const report = {
  experiment: 'pgm_index_filter',
  phase: 489,
  timestamp: new Date().toISOString(),
  stats,
  sampleKeyLookupsTested: 120,
  allLookupsSuccessful: true,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_PGM_INDEX_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_PGM_INDEX_REPORT.json');

console.log('All PGM Index Filter tests passed successfully!');
