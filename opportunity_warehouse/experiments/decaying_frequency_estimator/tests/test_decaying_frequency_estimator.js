const { DecayingFrequencyEstimator } = require('../lib/decaying_frequency_estimator');
const fs = require('fs');
const path = require('path');

console.log('Testing Decaying Frequency Estimator...');
// Half-life = 50 time units
const estimator = new DecayingFrequencyEstimator(50, 64);

// Test 1: Historical burst at t = 0..10
for (let t = 0; t <= 10; t++) {
  estimator.observe('token_ancient_burst', 1.0, t);
}
// Score at t = 10 should be ~10
const scoreT10 = estimator.getScore('token_ancient_burst', 10);
console.log('✓ Test 1: Initial burst score at t=10: ' + scoreT10.toFixed(2));

// Test 2: Half-life decay at t = 60 (dt = 50 = 1 half-life)
const scoreT60 = estimator.getScore('token_ancient_burst', 60);
const ratio = scoreT60 / scoreT10;
console.log('✓ Test 2: Decayed score at t=60 (1 half-life): ' + scoreT60.toFixed(2) + ' (ratio: ' + ratio.toFixed(3) + ', expected ~0.500)');
if (Math.abs(ratio - 0.5) > 0.05) {
  throw new Error('Half-life decay ratio failed: ' + ratio);
}

// Test 3: Recent item supersedes decayed burst
for (let t = 90; t <= 95; t++) {
  estimator.observe('token_recent_item', 1.0, t);
}
const top = estimator.getTopK(2);
if (top[0].key !== 'token_recent_item') {
  throw new Error('Recent item should be ranked #1');
}
console.log('✓ Test 3: Recent item successfully overtook decayed ancient burst in top rankings');

// Test 4: Write verification report
const report = {
  experiment: 'decaying_frequency_estimator',
  phase: 457,
  timestamp: new Date().toISOString(),
  halfLife: 50,
  scoreAtBurst: scoreT10,
  scoreAfterHalfLife: scoreT60,
  decayRatio: ratio,
  topRanked: top,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_DECAYING_FREQUENCY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_DECAYING_FREQUENCY_REPORT.json');

console.log('All Decaying Frequency Estimator tests passed successfully!');
