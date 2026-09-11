const { SlidingWindowHLL } = require('../lib/sliding_window_hll');
const fs = require('fs');
const path = require('path');

console.log('Testing Sliding Window HyperLogLog Estimator...');
const swhll = new SlidingWindowHLL(6, 50); // m = 64, window = 50 time units

// Test 1: Add 50 unique items at time t = 10
for (let i = 0; i < 50; i++) {
  swhll.add('token_batch_1_' + i, 10);
}
const est1 = swhll.estimate(10);
console.log('✓ Test 1: Cardinality estimate at t=10 for 50 items: ' + est1 + ' (expected ~50)');
if (est1 < 30 || est1 > 70) {
  throw new Error('Estimate outside acceptable bounds: ' + est1);
}

// Test 2: Add 50 new unique items at time t = 40 (Window now covers batch 1 and batch 2)
for (let i = 0; i < 50; i++) {
  swhll.add('token_batch_2_' + i, 40);
}
const est2 = swhll.estimate(40);
console.log('✓ Test 2: Cardinality estimate at t=40 for 100 items: ' + est2 + ' (expected ~100)');
if (est2 < 65 || est2 > 140) {
  throw new Error('Estimate outside acceptable bounds: ' + est2);
}

// Test 3: Advance time to t = 70.
// Window threshold is 70 - 50 = 20. Batch 1 (t=10) has completely expired!
// Only Batch 2 (t=40) should remain.
const est3 = swhll.estimate(70);
console.log('✓ Test 3: Cardinality estimate at t=70 after batch 1 expired: ' + est3 + ' (expected ~50)');
if (est3 < 30 || est3 > 75) {
  throw new Error('Estimate after expiration failed: ' + est3);
}

// Test 4: Verify memory footprint and pruning efficiency
const footprint = swhll.getMemoryFootprint();
console.log('✓ Test 4: Memory footprint: ' + footprint.totalEntries + ' total entries across 64 registers (avg ' + footprint.avgEntriesPerRegister.toFixed(2) + ' entries/reg)');
if (footprint.totalEntries > 256) {
  throw new Error('Memory footprint exceeded bounded space constraints');
}

// Write evidence report
const report = {
  experiment: 'sliding_window_hll',
  phase: 461,
  timestamp: new Date().toISOString(),
  precision: 6,
  registers: 64,
  windowSize: 50,
  batch1Estimate: est1,
  combinedEstimate: est2,
  postExpirationEstimate: est3,
  footprint,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_SLIDING_WINDOW_HLL_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_SLIDING_WINDOW_HLL_REPORT.json');

console.log('All Sliding Window HLL tests passed successfully!');
