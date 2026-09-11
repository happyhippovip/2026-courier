const { HyperLogLog } = require('../lib/hyperloglog_estimator');
const fs = require('fs');
const path = require('path');

console.log('Testing HyperLogLog Cardinality Estimator...');
// b = 6 -> m = 64 registers. Expected relative error ≈ 1.04 / sqrt(64) = 13%
const hll = new HyperLogLog(6);

// Test 1: Insert 500 distinct tokens
const uniqueCount = 500;
for (let i = 0; i < uniqueCount; i++) {
  hll.add('context_token_' + i);
}

// Add duplicate tokens to verify cardinality invariance
for (let i = 0; i < 200; i++) {
  hll.add('context_token_' + (i % 50));
}

const estimate = hll.estimate();
const errorPercent = Math.abs(estimate - uniqueCount) / uniqueCount * 100;
console.log('✓ Test 1: Estimated ' + estimate + ' distinct tokens for actual ' + uniqueCount + ' (Error: ' + errorPercent.toFixed(2) + '%)');
if (errorPercent > 25) {
  throw new Error('HyperLogLog error rate exceeded bounds: ' + errorPercent + '%');
}

// Test 2: Invariance to duplicate volume
if (hll.totalAdded !== 700) throw new Error('Total processed count incorrect');
console.log('✓ Test 2: Ingestion processed 700 events without inflating distinct cardinality beyond tolerance');

// Test 3: Small range linear counting check
const smallHll = new HyperLogLog(6);
for (let i = 0; i < 15; i++) smallHll.add('small_token_' + i);
const smallEst = smallHll.estimate();
console.log('✓ Test 3: Small range linear counting estimate: ' + smallEst + ' (actual: 15)');
if (Math.abs(smallEst - 15) > 5) throw new Error('Small range estimate out of bounds: ' + smallEst);

// Test 4: Write verification report
const report = {
  experiment: 'hyperloglog_estimator',
  phase: 425,
  timestamp: new Date().toISOString(),
  b: 6,
  registers: hll.m,
  actualUniqueTokens: uniqueCount,
  estimatedUniqueTokens: estimate,
  errorPercent: errorPercent.toFixed(2) + '%',
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_HYPERLOGLOG_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_HYPERLOGLOG_REPORT.json');

console.log('All HyperLogLog tests passed successfully!');
