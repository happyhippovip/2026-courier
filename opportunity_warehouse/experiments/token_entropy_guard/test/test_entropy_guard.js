const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TokenEntropyGuard } = require('../lib/entropy_guard');

const guard = new TokenEntropyGuard({ windowSize: 40, lowEntropyThreshold: 2.8, highEntropyThreshold: 5.0 });

// Test 1: Natural English sentence produces normal Shannon entropy (3.0 - 4.5)
const normalText = 'Autonomous revenue collection verified incoming payment euro five received.';
const resNormal = guard.evaluateWindow(normalText);
assert.strictEqual(resNormal.status, 'NORMAL', 'Natural language text must have NORMAL entropy');
assert.ok(resNormal.entropy >= 3.0 && resNormal.entropy <= 4.8, 'Entropy should fall within typical natural language bounds');
console.log('✓ Test 1: Natural text produced balanced entropy (' + resNormal.entropy + ' bits/char)');

// Test 2: Degenerate repetition loop collapses entropy (< 2.0)
const loopText = 'repeat repeat repeat repeat repeat repeat repeat repeat';
const resLoop = guard.evaluateWindow(loopText);
assert.strictEqual(resLoop.status, 'ANOMALY_LOW_ENTROPY', 'Repetitive loop must trigger ANOMALY_LOW_ENTROPY');
assert.strictEqual(resLoop.isLoop, true);
console.log('✓ Test 2: Repetitive loop triggered ANOMALY_LOW_ENTROPY (' + resLoop.entropy + ' bits/char)');

// Test 3: High-entropy pseudo-random noise triggers ANOMALY_HIGH_ENTROPY (> 5.0)
// Construct string with all distinct characters
let noiseText = '';
for (let c = 33; c < 33 + 40; c++) noiseText += String.fromCharCode(c);
const resNoise = guard.evaluateWindow(noiseText);
assert.strictEqual(resNoise.status, 'ANOMALY_HIGH_ENTROPY', 'Maximal diversity text must trigger ANOMALY_HIGH_ENTROPY');
assert.strictEqual(resNoise.isNoise, true);
console.log('✓ Test 3: High entropy noise triggered ANOMALY_HIGH_ENTROPY (' + resNoise.entropy + ' bits/char)');

// Test 4: Stream evaluation with halt recommendation and evidence write
const streamWithLoop = [
  'The autonomous agent is now executing the verification protocol. ',
  'All invariants are satisfied. ',
  'loop loop loop loop loop loop loop loop loop loop loop loop ',
  'loop loop loop loop loop loop loop loop loop loop loop loop '
];

const streamEval = guard.evaluateStream(streamWithLoop);
assert.strictEqual(streamEval.haltRecommended, true, 'Sustained loop should trigger halt recommendation');
assert.ok(streamEval.loopDetectedCount >= 2, 'Should detect at least 2 loop windows');

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_TOKEN_ENTROPY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  normalEvaluation: resNormal,
  loopEvaluation: resLoop,
  noiseEvaluation: resNoise,
  streamSummary: {
    totalLength: streamEval.totalLength,
    windowsEvaluated: streamEval.windowsEvaluated,
    loopDetectedCount: streamEval.loopDetectedCount,
    haltRecommended: streamEval.haltRecommended
  }
}, null, 2), 'utf8');
console.log('✓ Test 4: Stream evaluation successfully triggered halt signal and wrote evidence report');

console.log('All Token Entropy Guard tests passed successfully!');
