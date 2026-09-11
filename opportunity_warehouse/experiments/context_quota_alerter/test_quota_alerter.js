/**
 * test_quota_alerter.js - Test suite for Context Quota Alerter
 */
const assert = require('assert');
const { ContextQuotaAlerter } = require('./lib/quota_alerter');

console.log('--- Running test_quota_alerter.js ---');

const alerter = new ContextQuotaAlerter({ maxTokensPerSession: 1000, warningThresholdRatio: 0.80 });

// Test 1: Normal usage ingestion
const res1 = alerter.ingestPromptUsage(500, 'agent_1');
assert.strictEqual(res1.status, 'NORMAL');
assert.strictEqual(res1.isBlocked, false);
assert.strictEqual(res1.remainingTokens, 500);
console.log('✓ Test 1 Passed: Normal usage under threshold accepted');

// Test 2: Warning threshold trigger at >=80%
const res2 = alerter.ingestPromptUsage(350, 'agent_1'); // total 850 / 1000 = 85%
assert.strictEqual(res2.status, 'WARNING_THRESHOLD_EXCEEDED');
assert.strictEqual(res2.isBlocked, false);
assert.strictEqual(res2.remainingTokens, 150);
console.log('✓ Test 2 Passed: Warning threshold properly triggered at 85% capacity');

// Test 3: Circuit breaker trip at >=100%
const res3 = alerter.ingestPromptUsage(200, 'agent_1'); // total 1050 / 1000
assert.strictEqual(res3.status, 'CIRCUIT_BREAKER_TRIPPED');
assert.strictEqual(res3.isBlocked, true);
assert.strictEqual(res3.remainingTokens, 0);
console.log('✓ Test 3 Passed: Circuit breaker tripped on exceeding quota limit');

// Test 4: Reset functionality
const resetRes = alerter.resetSession();
assert.strictEqual(resetRes.status, 'RESET_SUCCESSFUL');
assert.strictEqual(alerter.currentTokensAccumulated, 0);
assert.strictEqual(alerter.isCircuitBreakerTripped, false);
console.log('✓ Test 4 Passed: Session reset cleans up accumulated counters');

console.log('ALL 4 TESTS PASSED IN test_quota_alerter.js\n');
