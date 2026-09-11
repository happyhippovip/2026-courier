const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { PromptAnomalyScorer } = require('../lib/anomaly_scorer');

console.log('--- Testing Prompt Anomaly & Drift Scorer ---');

const scorer = new PromptAnomalyScorer({ windowSize: 4, zScoreThreshold: 2.0 });

// Record standard stable turns
scorer.recordTurn(1, 4000, { system: 1000, rules: 500, tools: 1000, history: 500, user: 1000 });
scorer.recordTurn(2, 4200, { system: 1000, rules: 500, tools: 1000, history: 700, user: 1000 });
scorer.recordTurn(3, 4150, { system: 1000, rules: 500, tools: 1000, history: 800, user: 850 });
scorer.recordTurn(4, 4300, { system: 1000, rules: 500, tools: 1000, history: 1000, user: 800 });

// Test 1: Rolling baseline statistics
const stats = scorer.computeRollingStats();
assert.ok(stats.mean >= 4000 && stats.mean <= 4300, 'Rolling mean must be within expected range');
assert.ok(stats.stdDev >= 0, 'Standard deviation must be non-negative');
console.log('✓ Assertion 1 Passed: Rolling statistics baseline accurate (Mean: ' + stats.mean + ', StdDev: ' + stats.stdDev + ')');

// Test 2: Standard turn within threshold (no anomaly)
const normalEval = scorer.recordTurn(5, 4250, { system: 1000, rules: 500, tools: 1000, history: 1100, user: 650 });
assert.strictEqual(normalEval.isAnomaly, false, 'Turn 5 must not be flagged as an anomaly');
console.log('✓ Assertion 2 Passed: Nominal turn recognized without false positives');

// Test 3: Abrupt runaway token inflation (anomaly detected)
const runawayEval = scorer.recordTurn(6, 18500, { system: 1000, rules: 500, tools: 1000, history: 15000, user: 1000 });
assert.strictEqual(runawayEval.isAnomaly, true, 'Turn 6 runaway inflation must be flagged');
assert.ok(runawayEval.zScore > 2.0, 'Z-score must exceed threshold');
console.log('✓ Assertion 3 Passed: Runaway context explosion flagged (Z=' + runawayEval.zScore + ')');

// Test 4: Export audit report to evidence
const report = scorer.generateAuditReport();
assert.strictEqual(report.totalTurnsEvaluated, 6, 'All 6 turns must be audited');
assert.ok(report.anomalyCount >= 1, 'Must record at least 1 anomaly');

const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_PROMPT_ANOMALY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence file must exist');
console.log('✓ Assertion 4 Passed: Anomaly audit report exported to SAMPLE_PROMPT_ANOMALY_REPORT.json');

console.log('All 4 Prompt Anomaly Scorer tests passed successfully!');
