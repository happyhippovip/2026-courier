const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CompressionFidelityBenchmark } = require('../lib/fidelity_benchmark');

console.log('--- Testing Compression Ratio & Fidelity Benchmark ---');

const benchmark = new CompressionFidelityBenchmark();

const originalPrompt = [
  'SYSTEM_SECURITY_INVARIANT: ZERO_SPEND_POLICY = TRUE',
  'You are a high-performance assistant.',
  'Do not incur any financial charges or create cryptocurrency wallets.',
  'Here is a long redundant explanation about software development in general.',
  'Software is written in languages and compiled into machine instructions.',
  'Ensure all test suites pass with zero regressions.'
].join('\n');

const goodPrunedPrompt = [
  'SYSTEM_SECURITY_INVARIANT: ZERO_SPEND_POLICY = TRUE',
  'You are a high-performance assistant.',
  'Do not incur financial charges or create wallets.',
  'Ensure all test suites pass with zero regressions.'
].join('\n');

const badPrunedPrompt = [
  'You are a high-performance assistant.',
  'Software is written in languages.'
].join('\n');

const criticalInvariants = [
  'SYSTEM_SECURITY_INVARIANT: ZERO_SPEND_POLICY = TRUE',
  'zero regressions'
];

// Test 1: Invariant preservation verification on good prune
const checkGood = benchmark.checkInvariantPreservation(originalPrompt, goodPrunedPrompt, criticalInvariants);
assert.strictEqual(checkGood.allPreserved, true, 'Good prune must preserve 100% of critical invariants');
assert.strictEqual(checkGood.violationCount, 0);
console.log('✓ Assertion 1 Passed: 100% invariant preservation verified on good prune');

// Test 2: Invariant violation detection on bad prune
const checkBad = benchmark.checkInvariantPreservation(originalPrompt, badPrunedPrompt, criticalInvariants);
assert.strictEqual(checkBad.allPreserved, false, 'Bad prune must fail invariant check');
assert.strictEqual(checkBad.violationCount, 2, 'Bad prune violates 2 invariants');
console.log('✓ Assertion 2 Passed: Critical invariant violations flagged on degraded prune');

// Test 3: Quality index and acceptability evaluation
const evalGood = benchmark.evaluateFidelityBenchmark(originalPrompt, goodPrunedPrompt, criticalInvariants);
assert.strictEqual(evalGood.isAcceptable, true, 'Good prune must be deemed acceptable');
assert.ok(evalGood.qualityIndex >= 0.70, 'Quality index must meet threshold');
assert.ok(evalGood.tokenSavingsPercent > 20, 'Must achieve token savings');
console.log('✓ Assertion 3 Passed: Quality Index validated (Q=' + evalGood.qualityIndex + ', Savings: ' + evalGood.tokenSavingsPercent + '%)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_COMPRESSION_FIDELITY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evalGood, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_COMPRESSION_FIDELITY_REPORT.json');

console.log('All 4 Compression Fidelity Benchmark tests passed successfully!');