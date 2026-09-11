const assert = require('assert');
const { generateKeyPair, signLicense, verifyLicense } = require('../lib/license_signer');

console.log('Running Cryptographic License Signer Tests...');

// Setup test keys
const keys = generateKeyPair();
assert.ok(keys.publicKey.includes('BEGIN PUBLIC KEY'));
assert.ok(keys.privateKey.includes('BEGIN PRIVATE KEY'));
console.log('  [PASS] Test 1: ECDSA prime256v1 keypair generated');

// Test 2: Sign and verify license payload
const payload = {
  license_id: 'LIC-ENTERPRISE-2026-001',
  customer_email: 'enterprise@corp.com',
  seats: 25,
  tier: 'ENTERPRISE_TIER_1',
  issued_at: '2026-09-11T00:00:00.000Z'
};
const signed = signLicense(payload, keys.privateKey);
assert.ok(signed.signature);

const verification = verifyLicense(signed, keys.publicKey);
assert.strictEqual(verification.is_valid, true);
assert.strictEqual(verification.payload.customer_email, 'enterprise@corp.com');
console.log('  [PASS] Test 2: License signing and offline verification validated');

// Test 3: Tamper detection
const tamperedToken = JSON.parse(JSON.stringify(signed));
tamperedToken.payload.seats = 999; // Attacker attempts to forge 999 seats
const tamperedVerification = verifyLicense(tamperedToken, keys.publicKey);
assert.strictEqual(tamperedVerification.is_valid, false, 'Tampered payload must fail signature check');
console.log('  [PASS] Test 3: Cryptographic payload tampering detected');

// Test 4: Wrong key verification failure
const otherKeys = generateKeyPair();
const wrongKeyVerification = verifyLicense(signed, otherKeys.publicKey);
assert.strictEqual(wrongKeyVerification.is_valid, false, 'Verification with wrong public key must fail');
console.log('  [PASS] Test 4: Unrelated public key rejection confirmed');

console.log('ALL 4 LICENSE SIGNER TESTS PASSED DETERMINISTICALLY!');
