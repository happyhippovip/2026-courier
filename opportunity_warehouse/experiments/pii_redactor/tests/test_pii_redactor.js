const assert = require('assert');
const { PiiRedactor } = require('../lib/pii_redactor');

console.log('Testing PiiRedactor...');

const redactor = new PiiRedactor();

// Test 1: Email redaction
const t1 = 'Contact engineer at dev.lead@company.org regarding server.';
const r1 = redactor.redact(t1);
assert.strictEqual(r1.redactionCount, 1);
assert.strictEqual(r1.redactedText, 'Contact engineer at [REDACTED_EMAIL] regarding server.');

// Test 2: IP Address & Bearer token redaction
const t2 = 'Request from 192.168.1.100 with auth Bearer sk_live_secretkey9991.';
const r2 = redactor.redact(t2);
assert.strictEqual(r2.redactionCount, 2);
assert.ok(r2.redactedText.includes('[REDACTED_IP]'));
assert.ok(r2.redactedText.includes('Bearer [REDACTED_TOKEN]'));

// Test 3: Multiple entities
const t3 = 'Email: a@b.com, IP: 10.0.0.1, Phone: 555-123-4567';
const r3 = redactor.redact(t3);
assert.strictEqual(r3.redactionCount, 3);
assert.ok(!r3.redactedText.includes('a@b.com'));
assert.ok(!r3.redactedText.includes('10.0.0.1'));
assert.ok(!r3.redactedText.includes('555-123-4567'));

// Test 4: Empty input handling
const r4 = redactor.redact('');
assert.strictEqual(r4.redactionCount, 0);
assert.strictEqual(r4.redactedText, '');

console.log('All PiiRedactor tests passed (4/4)!');
