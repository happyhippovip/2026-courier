const assert = require('assert');
const { WebhookKeyRotator } = require('../lib/key_rotator');

console.log('Testing WebhookKeyRotator...');

const rotator = new WebhookKeyRotator('secret_alpha');

// Test 1: Valid primary verification
const payload = JSON.stringify({ order_id: 'GUM-100', price: '5.00' });
const sig1 = rotator.computeSignature(payload, 'secret_alpha');
const check1 = rotator.verifySignature(payload, sig1);
assert.strictEqual(check1.valid, true);
assert.strictEqual(check1.keyUsed, 'PRIMARY');

// Test 2: Secret rotation
rotator.rotateSecret('secret_beta');
assert.strictEqual(rotator.rotationHistory.length, 2);

// Test 3: Grace period verification with old key
const checkGrace = rotator.verifySignature(payload, sig1);
assert.strictEqual(checkGrace.valid, true);
assert.strictEqual(checkGrace.keyUsed, 'PREVIOUS_GRACE_PERIOD');

// Test 4: New key verification
const sig2 = rotator.computeSignature(payload, 'secret_beta');
const checkNew = rotator.verifySignature(payload, sig2);
assert.strictEqual(checkNew.valid, true);
assert.strictEqual(checkNew.keyUsed, 'PRIMARY');

// Test 5: Invalid signature fails gracefully without throwing
const checkBad = rotator.verifySignature(payload, 'invalid_sig_wrong_length');
assert.strictEqual(checkBad.valid, false);

console.log('All WebhookKeyRotator tests passed (5/5)!');
