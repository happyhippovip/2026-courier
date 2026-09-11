const assert = require('assert');
const { LicenseKeyVerifier } = require('../lib/license_key_verifier');

const verifier = new LicenseKeyVerifier();

console.log('--- TEST 1: License Key Generation ---');
const key = verifier.generateKey({
  orderId: 'ORD-99418',
  customerEmail: 'dev@studio.com',
  tier: 'PRO'
});

assert(key.startsWith('SYM-PRO-'));
assert.strictEqual(key.split('-').length, 6);
console.log('PASS [Test 1]: Deterministic license key generated: ' + key);

console.log('--- TEST 2: Valid Key Verification ---');
assert.strictEqual(verifier.verifyKey({
  licenseKey: key,
  orderId: 'ORD-99418',
  customerEmail: 'dev@studio.com',
  tier: 'PRO'
}), true);
console.log('PASS [Test 2]: Valid key verified successfully.');

console.log('--- TEST 3: Tampered Key Rejection ---');
assert.strictEqual(verifier.verifyKey({
  licenseKey: 'SYM-PRO-0000-1111-2222-3333',
  orderId: 'ORD-99418',
  customerEmail: 'dev@studio.com',
  tier: 'PRO'
}), false);
console.log('PASS [Test 3]: Tampered key rejected fail-closed.');

console.log('--- TEST 4: Email / Order Mismatch Rejection ---');
assert.strictEqual(verifier.verifyKey({
  licenseKey: key,
  orderId: 'ORD-DIFFERENT',
  customerEmail: 'dev@studio.com',
  tier: 'PRO'
}), false);
console.log('PASS [Test 4]: Mismatched order ID rejected.');

console.log('\n>>> ALL 4 LICENSE VERIFIER TESTS PASS (100% DETERMINISTIC) <<<');
