const { RadixSplineFilter } = require('../lib/radix_spline_filter');
const fs = require('fs');
const path = require('path');

console.log('Testing Radix Spline Index Filter...');

// Synthetic sorted sequence of 100 token keys with non-linear intervals
const sortedKeys = [];
let currentKey = 10;
for (let i = 0; i < 100; i++) {
  currentKey += Math.floor(Math.random() * 8) + 1;
  sortedKeys.push(currentKey);
}

const rs = new RadixSplineFilter(sortedKeys, 4, 4);

// Test 1: Spline construction and compression verification
const stats = rs.getStats();
console.log('✓ Test 1: RadixSpline constructed: ' + stats.splinePointsCount + ' spline knots for ' + stats.totalKeys + ' keys (knot ratio: ' + stats.compressionRatio + ')');
if (stats.splinePointsCount >= stats.totalKeys) {
  throw new Error('Spline did not compress points effectively');
}

// Test 2: Point lookup verification across all 100 keys
for (let i = 0; i < sortedKeys.length; i++) {
  const foundIdx = rs.lookup(sortedKeys[i]);
  if (foundIdx === -1 || sortedKeys[foundIdx] !== sortedKeys[i]) {
    throw new Error('Key lookup failed for key: ' + sortedKeys[i] + ' at index ' + i + ' (found: ' + foundIdx + ')');
  }
}
console.log('✓ Test 2: All 100 keys retrieved accurately with bounded spline prediction');

// Test 3: Missing key lookup returns -1
const missing = rs.lookup(999999);
console.log('✓ Test 3: Out-of-bounds missing key returned -1 accurately');
if (missing !== -1) {
  throw new Error('Missing key did not return -1');
}

// Test 4: Write verification report
const report = {
  experiment: 'radix_spline_filter',
  phase: 485,
  timestamp: new Date().toISOString(),
  stats,
  sampleKeyLookupsTested: 100,
  allLookupsSuccessful: true,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_RADIX_SPLINE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_RADIX_SPLINE_REPORT.json');

console.log('All Radix Spline Filter tests passed successfully!');
