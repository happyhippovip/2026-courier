const assert = require('assert');
const { triageFeedback } = require('../lib/feedback_dispatcher');

console.log('Running Feedback Dispatcher Tests...');

// Test 1: Standard feedback triage
const ticket1 = triageFeedback({
  email: 'dev@studio.com',
  category: 'FEATURE_REQUEST',
  message: 'Please add support for Windsurf .windsurfrules parser'
});
assert.strictEqual(ticket1.category, 'FEATURE_REQUEST');
assert.strictEqual(ticket1.urgency, 'NORMAL');
assert.strictEqual(ticket1.customer_email, 'dev@studio.com');
console.log('  [PASS] Test 1: Standard feature request triage verified');

// Test 2: Critical urgency heuristic
const ticketCrash = triageFeedback({
  email: 'user@bug.com',
  category: 'BUG',
  message: 'CLI throws SyntaxError and crash on nested brackets'
});
assert.strictEqual(ticketCrash.urgency, 'CRITICAL');
console.log('  [PASS] Test 2: Critical urgency detection verified');

// Test 3: Commercial opportunity heuristic
const ticketBiz = triageFeedback({
  email: 'cto@firm.com',
  category: 'GENERAL',
  message: 'We want an enterprise team license for 25 engineers with VAT invoice'
});
assert.strictEqual(ticketBiz.urgency, 'HIGH_COMMERCIAL_VALUE');
console.log('  [PASS] Test 3: High commercial value triage verified');

console.log('ALL 3 FEEDBACK DISPATCHER TESTS PASSED DETERMINISTICALLY!');
