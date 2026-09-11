const assert = require('assert');
const { generateDeliveryMessage } = require('../lib/delivery_notifier');

console.log('Running Customer Delivery Notifier Tests...');

// Test 1: Generate valid delivery payload
const delivery = generateDeliveryMessage({
  customer_email: 'buyer@studio.ai',
  order_id: 'GUM-ORD-12345',
  license_key: 'ACT-PROD-TEST-KEY-001'
});
assert.strictEqual(delivery.recipient, 'buyer@studio.ai');
assert.ok(delivery.subject.includes('GUM-ORD-12345'));
assert.ok(delivery.plain_text.includes('ACT-PROD-TEST-KEY-001'));
assert.ok(delivery.html.includes('buyer@studio.ai') || delivery.html.includes('Download agent-context-trimmer'));
console.log('  [PASS] Test 1: Delivery email generation verified');

// Test 2: SHA-256 verification inclusion
assert.ok(delivery.plain_text.includes('SHA-256 Checksum'));
assert.ok(delivery.html.includes('SHA-256 Hash'));
console.log('  [PASS] Test 2: Cryptographic checksum included in dispatch message');

// Test 3: Quick start CLI snippet inclusion
assert.ok(delivery.plain_text.includes('node bin/trimmer.js audit'));
assert.ok(delivery.html.includes('node bin/trimmer.js audit'));
console.log('  [PASS] Test 3: Quick start CLI instructions verified');

console.log('ALL 3 DELIVERY NOTIFIER TESTS PASSED DETERMINISTICALLY!');
