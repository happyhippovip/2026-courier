const assert = require('assert');
const { MockOrderGenerator } = require('../lib/mock_order_generator');

console.log('--- TEST 1: Single Mock Order Generation ---');
const order = MockOrderGenerator.generateOrder({ grossAmountEur: 5.00 });
assert(order.order_id.startsWith('ORD-TEST-'));
assert.strictEqual(order.gross_amount_eur, 5.00);
assert.strictEqual(order.currency, 'EUR');
assert.strictEqual(order.payment_status, 'PAID');
console.log('PASS [Test 1]: Valid mock order created: ' + order.order_id);

console.log('--- TEST 2: Batch Generation Uniqueness ---');
const batch = MockOrderGenerator.generateBatch(10);
assert.strictEqual(batch.length, 10);
const ids = new Set(batch.map(o => o.order_id));
assert.strictEqual(ids.size, 10, 'All order IDs in batch must be unique');
console.log('PASS [Test 2]: Batch generated 10 unique order IDs.');

console.log('--- TEST 3: Custom Country and Product ---');
const custom = MockOrderGenerator.generateOrder({
  productId: 'OPP-SEED-COURIER-07',
  grossAmountEur: 29.00,
  countryCode: 'FR'
});
assert.strictEqual(custom.product_id, 'OPP-SEED-COURIER-07');
assert.strictEqual(custom.gross_amount_eur, 29.00);
assert.strictEqual(custom.country_code, 'FR');
console.log('PASS [Test 3]: Custom order metadata preserved.');

console.log('\n>>> ALL 3 MOCK ORDER GENERATOR TESTS PASS (100% DETERMINISTIC) <<<');
