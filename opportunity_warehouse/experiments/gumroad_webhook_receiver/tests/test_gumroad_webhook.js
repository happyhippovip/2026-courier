const assert = require('assert');
const { GumroadWebhookHandler } = require('../lib/gumroad_webhook_handler');

const handler = new GumroadWebhookHandler({ webhookSecret: 'TEST_SECRET_123' });

console.log('--- TEST 1: Standard Gumroad Ping Normalization ---');
const rawPing = {
  sale_id: 'SALE-882194',
  product_permalink: 'agent-context-trimmer',
  product_name: 'agent-context-trimmer v1.0.0',
  price: 500, // 500 cents = €5.00
  currency: 'EUR',
  email: 'paying_dev@company.com',
  secret: 'TEST_SECRET_123'
};

const normalized = handler.verifyAndNormalize(rawPing);
assert.strictEqual(normalized.order_id, 'ORD-GUMROAD-SALE-882194');
assert.strictEqual(normalized.gross_amount_eur, 5.00);
assert.strictEqual(normalized.payment_status, 'PAID');
assert.strictEqual(normalized.customer_email, 'paying_dev@company.com');
console.log('PASS [Test 1]: Standard Gumroad ping normalized to canonical schema.');

console.log('--- TEST 2: Invalid Secret Rejection ---');
assert.throws(() => {
  handler.verifyAndNormalize({ ...rawPing, secret: 'WRONG_SECRET' });
}, /Invalid webhook secret/, 'Mismatched secret must throw');
console.log('PASS [Test 2]: Mismatched webhook secret rejected fail-closed.');

console.log('--- TEST 3: Missing Order ID Rejection ---');
assert.throws(() => {
  handler.verifyAndNormalize({ price: 500 });
}, /Missing sale_id/, 'Missing sale_id must throw');
console.log('PASS [Test 3]: Missing order ID rejected fail-closed.');

console.log('--- TEST 4: Zero / Negative Price Rejection ---');
assert.throws(() => {
  handler.verifyAndNormalize({ sale_id: '123', price: 0 });
}, /Invalid gross amount/, 'Zero price must throw');
console.log('PASS [Test 4]: Zero price rejected fail-closed.');

console.log('\n>>> ALL 4 GUMROAD WEBHOOK TESTS PASS (100% DETERMINISTIC) <<<');
