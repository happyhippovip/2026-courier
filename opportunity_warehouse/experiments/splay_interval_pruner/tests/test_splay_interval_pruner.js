const { SplayIntervalPruner } = require('../lib/splay_interval_pruner');
const fs = require('fs');
const path = require('path');

console.log('Testing Splay Interval Pruner...');
const pruner = new SplayIntervalPruner();

// Test 1: Insertion
pruner.insert(100, 300, 'chunk_a');
pruner.insert(50, 150, 'chunk_b');
pruner.insert(200, 500, 'chunk_c');
pruner.insert(10, 80, 'chunk_d');

if (pruner.size !== 4) throw new Error('Expected size 4, got ' + pruner.size);
console.log('✓ Test 1: Inserted 4 intervals into Splay Interval Tree');

// Test 2: Splay queryAccess moves queried element to root
const found = pruner.queryAccess(50);
if (!found || found.payload !== 'chunk_b') throw new Error('Expected chunk_b');
if (pruner.root.low !== 50) throw new Error('Splay failed: root should be 50, got ' + pruner.root.low);
console.log('✓ Test 2: Accessing interval 50 successfully splayed it to the root (accessCount: ' + pruner.root.accessCount + ')');

// Test 3: Overlap query
const overlaps = pruner.queryOverlap(70, 220);
const payloads = overlaps.map(o => o.payload).sort();
const expected = ['chunk_a', 'chunk_b', 'chunk_c', 'chunk_d'].sort();
if (JSON.stringify(payloads) !== JSON.stringify(expected)) {
  throw new Error('Overlap mismatch: ' + JSON.stringify(payloads));
}
console.log('✓ Test 3: Overlap query [70, 220] correctly intersected: ' + payloads.join(', '));

// Test 4: Write evidence report
const report = {
  experiment: 'splay_interval_pruner',
  phase: 397,
  timestamp: new Date().toISOString(),
  totalIntervals: pruner.size,
  currentRootPayload: pruner.root.payload,
  rootAccessCount: pruner.root.accessCount,
  overlapHits: payloads,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_SPLAY_INTERVAL_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_SPLAY_INTERVAL_REPORT.json');

console.log('All Splay Interval Pruner tests passed successfully!');
