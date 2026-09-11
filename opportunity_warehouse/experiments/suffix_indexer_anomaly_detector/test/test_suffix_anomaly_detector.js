const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SuffixAnomalyDetector } = require('../lib/suffix_anomaly_detector');

const detector = new SuffixAnomalyDetector({ maxDepth: 3, anomalyThreshold: 0.70 });

// Test 1: Normal natural text maintains low anomaly score (< 0.4)
const naturalText = 'Autonomous revenue settlement daemon verified incoming payment for commercial product release candidate.';
const resNatural = detector.analyze(naturalText);
assert.strictEqual(resNatural.quarantined, false, 'Natural text must not be quarantined');
assert.ok(resNatural.anomalyScore < 0.40, 'Natural text anomaly score must be low (got ' + resNatural.anomalyScore + ')');
console.log('✓ Test 1: Natural text produced low anomaly score (' + resNatural.anomalyScore + ')');

// Test 2: Degenerative repetitive loop triggers quarantine (> 0.70)
const loopText = 'loop loop loop loop loop loop loop loop loop loop loop loop loop loop loop';
const resLoop = detector.analyze(loopText);
assert.strictEqual(resLoop.quarantined, true, 'Degenerate loop must be quarantined');
assert.ok(resLoop.anomalyScore > 0.85, 'Loop anomaly score must be high (got ' + resLoop.anomalyScore + ')');
console.log('✓ Test 2: Repetitive loop quarantined (anomaly score: ' + resLoop.anomalyScore + ')');

// Test 3: Mixed text with normal diversity
const mixedText = 'System execution check complete: 143 test suites passing green with zero regressions.';
const resMixed = detector.analyze(mixedText);
assert.strictEqual(resMixed.quarantined, false);
console.log('✓ Test 3: Mixed technical text passed without quarantine (' + resMixed.anomalyScore + ')');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SUFFIX_ANOMALY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  naturalResult: resNatural,
  loopResult: resLoop,
  mixedResult: resMixed,
  totalWindowsAnalyzed: detector.totalWindows
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_SUFFIX_ANOMALY_REPORT.json');

console.log('All Suffix Anomaly Detector tests passed successfully!');
