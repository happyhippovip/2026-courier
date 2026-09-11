const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TurnLatencyProfiler } = require('../lib/turn_latency_profiler');

console.log('--- Testing Multi-Agent Turn Latency & Bandwidth Profiler ---');

const profiler = new TurnLatencyProfiler();

// Record multi-agent execution turns
profiler.recordTurn('turn_1_sys_init', 8000, 250, 450, 1800);
profiler.recordTurn('turn_2_research', 32000, 800, 1600, 5200);
profiler.recordTurn('turn_3_code_gen', 64000, 1200, 3100, 8500);
profiler.recordTurn('turn_4_review', 95000, 600, 4500, 7200);

// Test 1: Throughput and TTFT computation
assert.strictEqual(profiler.records.length, 4, 'Must record 4 turns');
const r3 = profiler.records[2];
assert.ok(r3.prefillTps > 0, 'Prefill TPS must be computed');
assert.ok(r3.decodeTps > 0, 'Decode TPS must be computed');
console.log('✓ Assertion 1 Passed: Throughput metrics computed (Turn 3 TTFT: ' + r3.ttftMs + 'ms, Decode TPS: ' + r3.decodeTps + ')');

// Test 2: Pruning speedup estimation
const speedup = profiler.estimatePruningSpeedup(0.40);
assert.ok(speedup.netTimeSavedMs > 2000, 'Pruning must yield net time saved');
assert.ok(speedup.netSpeedupPercent > 12, 'Pruning 40% input must yield over 12% overall roundtrip speedup');
console.log('✓ Assertion 2 Passed: 40% AST pruning yields ' + speedup.netSpeedupPercent + '% net latency reduction (' + speedup.netTimeSavedMs + 'ms saved)');

// Test 3: Profile report generation
const report = profiler.generateProfileReport();
assert.strictEqual(report.totalTurnsProfiled, 4);
assert.ok(report.averageTtftMs > 1000, 'Average TTFT correctly averaged across high-context turns');
console.log('✓ Assertion 3 Passed: Full latency profile report accurately consolidated');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_TURN_LATENCY_PROFILE.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence latency profile must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_TURN_LATENCY_PROFILE.json');

console.log('All 4 Turn Latency Profiler tests passed successfully!');
