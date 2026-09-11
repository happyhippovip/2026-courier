/**
 * test_canary_validator.js - Test suite for Canary Validator
 */
const assert = require('assert');
const { CanaryValidator } = require('./lib/canary_validator');

console.log('--- Running test_canary_validator.js ---');

const validator = new CanaryValidator({ maxAllowedRisk: 0.0 });

const cleanFixture = {
  name: 'auth_service.js',
  content: 'function authenticate(user) {\n  // DEBUG: login attempt\n  return user.isValid;\n}'
};

const safeRules = [
  { id: 'strip_debug_comments', pattern: '// DEBUG:.*', action: 'trim' }
];

const dangerousRules = [
  { id: 'wipe_functions', pattern: 'function.*\\{', action: 'trim' } // drops function keyword
];

// Test 1: Safe rules pass with zero risk
const run1 = validator.executeCanary([cleanFixture], safeRules);
assert.strictEqual(run1.summary.isApproved, true, 'Safe rules must be approved');
assert.strictEqual(run1.summary.averageRiskIndex, 0.0, 'Safe rules must have 0.0 risk');
assert.ok(run1.summary.authorizationToken.startsWith('ROLLBACK_AUTH_'), 'Authorization token must be generated');
console.log('✓ Test 1 Passed: Safe rules pass with zero risk and valid auth token');

// Test 2: Dangerous rules break syntax and are blocked
const run2 = validator.executeCanary([cleanFixture], dangerousRules);
assert.strictEqual(run2.summary.isApproved, false, 'Dangerous rules must be rejected');
assert.ok(run2.summary.averageRiskIndex > 0.3, 'Risk index must be high');
assert.strictEqual(run2.summary.authorizationToken, null, 'No token should be issued when risk is detected');
console.log('✓ Test 2 Passed: Dangerous rules flagged and blocked without token');

// Test 3: Unbalanced braces check triggers high risk
const brokenFixture = {
  name: 'broken.js',
  content: 'function test() { return 1;' // missing closing brace
};
const run3 = validator.executeCanary([brokenFixture], safeRules);
assert.strictEqual(run3.summary.isApproved, false, 'Broken syntax must not be approved');
assert.ok(run3.summary.averageRiskIndex >= 0.6, 'Unbalanced braces should incur high risk penalty');
console.log('✓ Test 3 Passed: Syntax brace mismatch detected with high penalty');

// Test 4: Batch evaluation across multiple fixtures
const fixtures = [
  cleanFixture,
  { name: 'user_controller.js', content: 'function getUser() { return { id: 1 }; }' }
];
const run4 = validator.executeCanary(fixtures, safeRules);
assert.strictEqual(run4.fixturesResults.length, 2, 'Must evaluate all fixtures in batch');
assert.strictEqual(run4.summary.isApproved, true, 'Batch must pass if all individual fixtures pass');
console.log('✓ Test 4 Passed: Multi-fixture batch evaluation succeeds cleanly');

console.log('ALL 4 TESTS PASSED IN test_canary_validator.js\n');
