const { CountMinMeanSketch } = require('../lib/count_min_mean_sketch');
const fs = require('fs');
const path = require('path');

console.log('Testing Count-Min-Mean Sketch Evaluator...');
const sketch = new CountMinMeanSketch(128, 5);

// Stream items:
// 'token_high_freq': 500
// 'token_med_freq': 150
// 'token_low_freq': 20
// 1000 background noise tokens (1 each)
sketch.add('token_high_freq', 500);
sketch.add('token_med_freq', 150);
sketch.add('token_low_freq', 20);

for (let i = 0; i < 1000; i++) {
  sketch.add('noise_token_' + i, 1);
}

// Test 1: High frequency token estimate accuracy
const estHigh = sketch.estimate('token_high_freq');
const errHigh = Math.abs(estHigh - 500) / 500 * 100;
console.log('✓ Test 1: High frequency estimate: ' + estHigh + ' (actual: 500, error: ' + errHigh.toFixed(2) + '%)');
if (errHigh > 10) throw new Error('High frequency estimate error too large');

// Test 2: Medium frequency token estimate accuracy
const estMed = sketch.estimate('token_med_freq');
const errMed = Math.abs(estMed - 150) / 150 * 100;
console.log('✓ Test 2: Medium frequency estimate: ' + estMed + ' (actual: 150, error: ' + errMed.toFixed(2) + '%)');
if (errMed > 15) throw new Error('Medium frequency estimate error too large');

// Test 3: Zero-count item should estimate near 0 despite 1000 noise tokens
const estZero = sketch.estimate('unseen_alien_token');
console.log('✓ Test 3: Unseen token estimate: ' + estZero + ' (unbiased zero-suppression)');
if (estZero > 10) throw new Error('Unseen token estimate should be near 0');

// Test 4: Write verification report
const report = {
  experiment: 'count_min_mean_sketch',
  phase: 445,
  timestamp: new Date().toISOString(),
  width: sketch.width,
  depth: sketch.depth,
  totalEvents: sketch.totalCount,
  testedEstimates: {
    high: { actual: 500, estimated: estHigh },
    med: { actual: 150, estimated: estMed },
    zero: { actual: 0, estimated: estZero }
  },
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_COUNT_MIN_MEAN_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_COUNT_MIN_MEAN_REPORT.json');

console.log('All Count-Min-Mean Sketch tests passed successfully!');
