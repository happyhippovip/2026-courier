const assert = require('assert');
const { simulateWebhookDelivery } = require('../lib/webhook_monitor');

console.log('Running Webhook Health Monitor Tests...');

// Test 1: Successful immediate delivery
const okDelivery = simulateWebhookDelivery('https://api.gumroad.com/webhook', { test: true }, { mockStatus: 200 });
assert.strictEqual(okDelivery.delivered, true);
assert.strictEqual(okDelivery.total_attempts, 1);
assert.strictEqual(okDelivery.dead_letter, false);
console.log('  [PASS] Test 1: Successful immediate delivery verified');

// Test 2: Retry with dead-letter queue
const failedDelivery = simulateWebhookDelivery('https://down.example.com/webhook', { test: true }, { mockStatus: 500, maxRetries: 3 });
assert.strictEqual(failedDelivery.delivered, false);
assert.strictEqual(failedDelivery.dead_letter, true);
assert.strictEqual(failedDelivery.total_attempts, 3);
console.log('  [PASS] Test 2: Dead-letter queue transition upon exhaustion confirmed');

// Test 3: Exponential backoff calculation
assert.strictEqual(failedDelivery.attempts[0].backoff_delay_ms, 0);
assert.strictEqual(failedDelivery.attempts[1].backoff_delay_ms, 2000);
assert.strictEqual(failedDelivery.attempts[2].backoff_delay_ms, 4000);
console.log('  [PASS] Test 3: Exponential backoff timing verified');

console.log('ALL 3 WEBHOOK HEALTH MONITOR TESTS PASSED DETERMINISTICALLY!');
