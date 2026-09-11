const assert = require('assert');
const { generateRetentionDigest } = require('../lib/retention_digest');

console.log('Running Customer Retention Digest Tests...');

// Test 1: Standard digest generation
const digest = generateRetentionDigest({ email: 'user@test.org', tokensSavedTotal: 50000, dollarsSavedEst: 15.00 });
assert.ok(digest.includes('user@test.org'));
assert.ok(digest.includes('50,000'));
assert.ok(digest.includes('$15.00'));
console.log('  [PASS] Test 1: Retention digest statistics verified');

// Test 2: Commercial value ladder promotion
assert.ok(digest.includes('pgvector-local-kit'));
assert.ok(digest.includes('@symphony/agent-locks'));
console.log('  [PASS] Test 2: Value ladder cross-sell included');

// Test 3: Clean HTML structure
assert.ok(digest.includes('<!DOCTYPE html>'));
assert.ok(digest.includes('stat-box'));
console.log('  [PASS] Test 3: Responsive styling verified');

console.log('ALL 3 CUSTOMER RETENTION TESTS PASSED DETERMINISTICALLY!');
