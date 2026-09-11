/**
 * test_benchmark_harness.js - Test suite for Prompt Benchmark Harness
 */
const assert = require('assert');
const { PromptBenchmarkHarness } = require('./lib/benchmark_harness');

console.log('--- Running test_benchmark_harness.js ---');

const harness = new PromptBenchmarkHarness({ minAcceptableRetention: 0.95 });

// Test 1: Clean compression retains 100% symbols and keywords
const goodCase = {
  id: 'case_auth_service',
  rawPrompt: 'SYSTEM:\n[DEBUG LOG]: Connecting to DB\n----------------\nfunction authenticate(user) { return user.token; }',
  trimmedPrompt: 'SYSTEM:\nfunction authenticate(user) { return user.token; }',
  requiredSymbols: ['authenticate', 'user.token'],
  expectedKeywords: ['SYSTEM'],
  prohibitedPatterns: ['DEBUG LOG', '----------------']
};

const res1 = harness.evaluateTestCase(goodCase);
assert.strictEqual(res1.passed, true, 'Good case must pass');
assert.strictEqual(res1.symbolRetentionRate, 1.0, 'All symbols must be retained');
assert.strictEqual(res1.noiseRemovalRate, 1.0, 'All noise must be pruned');
console.log('✓ Test 1 Passed: Perfect semantic preservation and 100% noise removal');

// Test 2: Overly aggressive trimming drops critical symbol
const brokenCase = {
  id: 'case_broken_trim',
  rawPrompt: 'function processOrder(order) { return order.id; }',
  trimmedPrompt: 'function (order) { return; }', // stripped processOrder & order.id
  requiredSymbols: ['processOrder', 'order.id'],
  expectedKeywords: ['function']
};

const res2 = harness.evaluateTestCase(brokenCase);
assert.strictEqual(res2.passed, false, 'Broken case must fail');
assert.ok(res2.missingSymbols.length > 0, 'Missing symbols must be recorded');
console.log('✓ Test 2 Passed: Accurately catches dropped code symbols');

// Test 3: Unpruned noise detection
const leakyCase = {
  id: 'case_leaky_noise',
  rawPrompt: 'DEBUG_TRACE: 1234\nCode',
  trimmedPrompt: 'DEBUG_TRACE: 1234\nCode',
  prohibitedPatterns: ['DEBUG_TRACE']
};

const res3 = harness.evaluateTestCase(leakyCase);
assert.strictEqual(res3.noiseRemovalRate, 0.0, 'Noise removal must be 0% when noise remains');
assert.ok(res3.remainingNoise.includes('DEBUG_TRACE'), 'Remaining noise pattern identified');
console.log('✓ Test 3 Passed: Detects unpruned noise patterns');

// Test 4: Suite aggregation
const suite = harness.runSuite([goodCase, goodCase]);
assert.strictEqual(suite.summary.allPassed, true, 'Suite with good cases must pass');
assert.strictEqual(suite.summary.totalCases, 2, 'Two cases evaluated');
assert.ok(suite.summary.averageCompressionRatioPercent > 20, 'Compression ratio tracked');
console.log('✓ Test 4 Passed: Full benchmark suite aggregation operates accurately');

console.log('ALL 4 TESTS PASSED IN test_benchmark_harness.js\n');
