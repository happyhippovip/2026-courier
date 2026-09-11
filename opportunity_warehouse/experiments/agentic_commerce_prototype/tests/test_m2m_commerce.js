const assert = require('assert');
const { M2MCommerceValidator } = require('../lib/m2m_checkout_validator');

const catalog = {
  'OPP-SEED-DIGITAL-01': 5.00,
  'OPP-SEED-CONTENT-03': 9.00,
  'OPP-SEED-COURIER-07': 29.00
};

const validator = new M2MCommerceValidator();

console.log('--- TEST 1: Quote Generation & Cryptographic Nonce ---');
const quote = validator.validateQuoteRequest({
  productId: 'OPP-SEED-DIGITAL-01',
  agentPublicKey: 'ed25519-agent-key-alpha',
  maxBudgetEur: 10.00,
  availableProducts: catalog
});

assert(quote.quoteId.startsWith('QUOTE-'));
assert.strictEqual(quote.priceEur, 5.00);
assert(quote.signature.length === 64);
console.log('PASS [Test 1]: Valid quote generated with HMAC-SHA256 signature.');

console.log('--- TEST 2: Budget Rejection Fail-Closed ---');
assert.throws(() => {
  validator.validateQuoteRequest({
    productId: 'OPP-SEED-COURIER-07',
    agentPublicKey: 'ed25519-agent-key-beta',
    maxBudgetEur: 15.00, // Tool costs €29
    availableProducts: catalog
  });
}, /Insufficient agent budget/, 'Under-budget quote request must throw');
console.log('PASS [Test 2]: Under-budget quote request rejected fail-closed.');

console.log('--- TEST 3: License Token Issuance on Verified Payment ---');
const validPaymentProof = {
  paymentId: 'PAY-SEPA-99881',
  verified: true,
  amountEur: 5.00
};

const license = validator.issueLicenseToken({
  quote,
  agentId: 'AGENT-RUNNER-001',
  paymentProof: validPaymentProof
});

assert(license.licenseId.startsWith('LIC-OPP-SEED-DIGITAL-01'));
assert(license.licenseToken.length === 64);
assert.strictEqual(license.priceEur, 5.00);
console.log('PASS [Test 3]: License token successfully issued.');

console.log('--- TEST 4: Offline Verification of Issued Token ---');
assert.strictEqual(validator.verifyLicenseOffline(license), true);
assert.strictEqual(validator.verifyLicenseOffline({ ...license, licenseToken: 'tampered' }), false);
console.log('PASS [Test 4]: Offline token validation is 100% deterministic and tamper-evident.');

console.log('--- TEST 5: Tampered Quote Signature Rejection ---');
assert.throws(() => {
  validator.issueLicenseToken({
    quote: { ...quote, signature: 'bad_sig' },
    agentId: 'AGENT-RUNNER-001',
    paymentProof: validPaymentProof
  });
}, /Quote signature mismatch/, 'Tampered quote must throw');
console.log('PASS [Test 5]: Tampered quote signature rejected fail-closed.');

console.log('\n>>> ALL 5 M2M AGENTIC COMMERCE TESTS PASS (100% DETERMINISTIC) <<<');
