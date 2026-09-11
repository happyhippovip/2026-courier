const assert = require('assert');
const { SupportRouter } = require('../lib/support_router');

console.log('Testing SupportRouter...');

const router = new SupportRouter();

// Test 1: License issue routing
const ticket1 = router.routeTicket({
  subject: 'License key activation error',
  body: 'My Gumroad receipt gave me a key but the CLI says invalid license.'
});
assert.strictEqual(ticket1.category, 'LICENSE_VERIFICATION');
assert.strictEqual(ticket1.priority, 'HIGH');
assert.ok(ticket1.automatedResponse.includes('--license-key'));

// Test 2: AST Parser error routing
const ticket2 = router.routeTicket({
  subject: 'Parse error in YAML block',
  body: 'When trimming my prompt, the syntax error occurred on line 42 with corrupted code block.'
});
assert.strictEqual(ticket2.category, 'AST_PARSER_ERROR');
assert.strictEqual(ticket2.priority, 'CRITICAL');
assert.ok(ticket2.automatedResponse.includes('--dump-ast'));

// Test 3: General fallback inquiry
const ticket3 = router.routeTicket({
  subject: 'Hello team',
  body: 'Just wanted to say hello from Berlin.'
});
assert.strictEqual(ticket3.category, 'GENERAL_INQUIRY');
assert.strictEqual(ticket3.priority, 'LOW');

console.log('All SupportRouter tests passed (3/3)!');
