const { HyperLogLogPlus } = require('../lib/hyperloglog_plus_estimator');
const fs = require('fs');
const path = require('path');

console.log('Testing HyperLogLog++ Estimator...');
// p = 8 -> 256 registers, sparseThreshold = 50
const hllp = new HyperLogLogPlus(8, 50);

// Test 1: Sparse mode exact cardinality
for (let i = 0; i < 30; i++) {
  hllp.add('sparse_token_' + i);
}
if (!hllp.isSparse) throw new Error('Should be in sparse mode');
const sparseEst = hllp.estimate();
if (sparseEst !== 30) throw new Error('Sparse estimate must be exact 30, got ' + sparseEst);
console.log('✓ Test 1: Sparse mode exact cardinality = 30 verified');

// Test 2: Transition to Dense mode
for (let i = 30; i < 200; i++) {
  hllp.add('dense_token_' + i);
}
if (hllp.isSparse) throw new Error('Should have converted to dense mode');
console.log('✓ Test 2: Successfully converted to dense representation after exceeding threshold');

// Test 3: Dense mode estimate accuracy (200 unique tokens)
const denseEst = hllp.estimate();
const err = Math.abs(denseEst - 200) / 200 * 100;
console.log('✓ Test 3: Dense estimate: ' + denseEst + ' (actual: 200, error: ' + err.toFixed(2) + '%)');
if (err > 15) throw new Error('Dense estimate error too high: ' + err + '%');

// Test 4: Write verification report
const report = {
  experiment: 'hyperloglog_plus_estimator',
  phase: 441,
  timestamp: new Date().toISOString(),
  p: 8,
  registers: hllp.m,
  isSparseNow: hllp.isSparse,
  totalAddedTokens: hllp.totalAdded,
  estimatedCardinality: denseEst,
  actualCardinality: 200,
  errorPercent: err.toFixed(2) + '%',
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_HLL_PLUS_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_HLL_PLUS_REPORT.json');

console.log('All HyperLogLog++ tests passed successfully!');
