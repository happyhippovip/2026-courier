const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { EMALatencyEstimator } = require('./lib/ema_latency_estimator');

console.log('Testing EMA Context Latency Estimator...');

const estimator = new EMALatencyEstimator(0.25, 2.5);

// Test 1: Initial observation establishes baseline
const obs1 = estimator.observe(10.0);
assert.strictEqual(obs1.ema, 10.0);
assert.strictEqual(obs1.isOutlier, false);
console.log('✓ Test 1: Initial baseline established');

// Test 2: Sequence of stable latency observations
for (let i = 0; i < 20; i++) {
  estimator.observe(10.0 + (i % 2 === 0 ? 0.5 : -0.5));
}
const stableMetrics = estimator.getMetrics();
assert.ok(Math.abs(stableMetrics.currentEMA - 10.0) < 0.5);
console.log('✓ Test 2: Stable sequence convergence verified (EMA: ' + stableMetrics.currentEMA + ' ms)');

// Test 3: Outlier spike detection and damping
const outlierObs = estimator.observe(150.0); // 15x spike
assert.strictEqual(outlierObs.isOutlier, true);
// Dampening prevented EMA from jumping to crazy values
assert.ok(outlierObs.ema < 25.0);
console.log('✓ Test 3: 150ms outlier spike detected and successfully dampened (EMA dampened to: ' + outlierObs.ema + ' ms)');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 301,
  component: 'ema_latency_estimator',
  observations: estimator.sampleCount,
  finalMetrics: estimator.getMetrics(),
  outlierDampingVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_EMA_LATENCY_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_EMA_LATENCY_REPORT.json');
console.log('All EMA Latency Estimator tests passed successfully!');
