const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ContextRateLimiter } = require('../lib/rate_limiter');

console.log('--- Testing Multi-Tenant Context Quota Rate Limiter ---');

const limiter = new ContextRateLimiter();
let simulatedClock = 1000000; // baseline ms
limiter.registerTenant('tenant_corp_a', { capacity: 20000, leakRatePerSec: 2000, initialTimestamp: simulatedClock });

// Test 1: Initial token consumption within capacity
const r1 = limiter.consumeTokens('tenant_corp_a', 15000, simulatedClock);
assert.strictEqual(r1.allowed, true, 'Request 1 within capacity must be allowed');
assert.strictEqual(r1.currentFillLevel, 15000);
console.log('✓ Assertion 1 Passed: Initial burst within capacity permitted');

// Test 2: Burst limit rejection on overflow
const r2 = limiter.consumeTokens('tenant_corp_a', 10000, simulatedClock);
assert.strictEqual(r2.allowed, false, 'Request 2 overflowing capacity must be rejected');
assert.ok(r2.retryAfterMs > 0, 'Must provide positive retryAfterMs');
console.log('✓ Assertion 2 Passed: Over-capacity burst rejected with retry-after (' + r2.retryAfterMs + 'ms)');

// Test 3: Leaky bucket refill over simulated elapsed time
simulatedClock += 5000; // advance 5 seconds -> leaks 5 * 2000 = 10000 tokens
const r3 = limiter.consumeTokens('tenant_corp_a', 10000, simulatedClock);
assert.strictEqual(r3.allowed, true, 'Request 3 must be allowed after bucket leaked');
assert.strictEqual(r3.currentFillLevel, 15000, 'Bucket fill level should be 5000 + 10000 = 15000');
console.log('✓ Assertion 3 Passed: Leaky bucket refilled after simulated time elapsed');

// Test 4: Export evidence JSON
const audit = limiter.generateAuditReport();
assert.strictEqual(audit.activeTenants, 1);
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_RATE_LIMITER_AUDIT.json');
fs.writeFileSync(evidencePath, JSON.stringify(audit, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence audit file must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_RATE_LIMITER_AUDIT.json');

console.log('All 4 Context Rate Limiter tests passed successfully!');