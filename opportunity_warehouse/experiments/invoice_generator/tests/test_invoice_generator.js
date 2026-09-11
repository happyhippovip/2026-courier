const assert = require('assert');
const { renderInvoiceHtml } = require('../lib/invoice_renderer');

console.log('Running Commercial Invoice Renderer Tests...');

// Test 1: Standard invoice render
const html = renderInvoiceHtml({
  order_id: 'ORD-TEST-999',
  customer_email: 'dev@test.org',
  amount_eur: 5.00
});
assert.ok(html.includes('ORD-TEST-999'), 'Must contain order ID');
assert.ok(html.includes('dev@test.org'), 'Must contain customer email');
assert.ok(html.includes('€5.00 EUR'), 'Must contain formatted total price');
console.log('  [PASS] Test 1: Standard invoice fields verified');

// Test 2: Paid status and badge
assert.ok(html.includes('PAID & SETTLED'), 'Must indicate paid status badge');
console.log('  [PASS] Test 2: Payment status confirmed');

// Test 3: Custom license key formatting
const customHtml = renderInvoiceHtml({ license_key_hash: 'ACT-CUSTOM-HASH-123' });
assert.ok(customHtml.includes('ACT-CUSTOM-HASH-123'), 'Must contain custom license key');
console.log('  [PASS] Test 3: License key fingerprint rendered');

console.log('ALL 3 INVOICE RENDERER TESTS PASSED DETERMINISTICALLY!');
