const assert = require('assert');
const { calculateLatencyMs, simulateSavings, PROVIDER_METRICS } = require('../lib/latency_simulator');

console.log('Running Token Latency Simulator Tests...');

// Test 1: Latency calculation
const sonnetLatency = calculateLatencyMs(2000, 'claude_3_5_sonnet');
assert.ok(sonnetLatency > 320, 'Latency must include base overhead and processing time');
console.log('  [PASS] Test 1: Latency calculation verified');

// Test 2: Standard savings simulation (2,000 -> 1,120 tokens, -44%)
const sim = simulateSavings(2000, 1120, 1500);
assert.strictEqual(sim.scenario.tokens_saved_per_request, 880);
assert.strictEqual(sim.scenario.reduction_percent, 44.0);
assert.ok(sim.providers.claude_3_5_sonnet.monthly_cost_saved_usd > 0, 'Must show positive cost savings');
console.log('  [PASS] Test 2: Savings simulation metrics validated');

// Test 3: Validation checks
assert.throws(() => simulateSavings(500, 1000), /Original tokens must be greater/, 'Should reject invalid token counts');
console.log('  [PASS] Test 3: Input validation bounds enforced');

// Test 4: All providers modeled
for (const key of Object.keys(PROVIDER_METRICS)) {
  assert.ok(sim.providers[key], `Provider ${key} must be modeled`);
}
console.log('  [PASS] Test 4: Multi-provider coverage verified');

console.log('ALL 4 TOKEN LATENCY TESTS PASSED DETERMINISTICALLY!');
