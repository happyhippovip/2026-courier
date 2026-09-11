const assert = require('assert');
const { CanaryEvaluator } = require('../lib/canary_evaluator');

console.log('Testing CanaryEvaluator...');

const evaluator = new CanaryEvaluator({ minAccuracyThreshold: 0.95 });

// Test suite for evaluation
const mockSuite = [
  {
    name: 'Preserves JSON schema directives',
    assertionFn: (trimmed) => trimmed.includes('response_format: json')
  },
  {
    name: 'Preserves critical API key placeholder',
    assertionFn: (trimmed) => trimmed.includes('AUTH_HEADER')
  },
  {
    name: 'Reduces total length',
    assertionFn: (trimmed, orig) => trimmed.length < orig.length
  }
];

// Test 1: Successful canary
const original = 'System prompt with response_format: json and AUTH_HEADER. ' + 'Extra bloat. '.repeat(50);
const trimmedGood = 'System prompt with response_format: json and AUTH_HEADER.';
const resultGood = evaluator.evaluatePromptPair(original, trimmedGood, mockSuite);
assert.strictEqual(resultGood.passed, true);
assert.strictEqual(resultGood.rollbackRecommended, false);
assert.strictEqual(resultGood.passedTests, 3);

// Test 2: Failing canary (dropped directive)
const trimmedBad = 'System prompt with AUTH_HEADER only.';
const resultBad = evaluator.evaluatePromptPair(original, trimmedBad, mockSuite);
assert.strictEqual(resultBad.passed, false);
assert.strictEqual(resultBad.rollbackRecommended, true);
assert.strictEqual(resultBad.passedTests, 2);

// Test 3: Report generation
const report = evaluator.generateCanaryReport(resultGood, { environment: 'staging' });
assert.strictEqual(report.status, 'CANARY_PROMOTED_TO_PRODUCTION');

console.log('All CanaryEvaluator tests passed (3/3)!');
