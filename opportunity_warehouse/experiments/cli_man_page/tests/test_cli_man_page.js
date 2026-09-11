const assert = require('assert');
const { renderPlaintextManPage } = require('../lib/man_page_renderer');

console.log('Running CLI Man Page Renderer Tests...');

// Test 1: Render standard man page
const man = renderPlaintextManPage({ version: 'v1.0.0' });
assert.ok(man.includes('AGENT-CONTEXT-TRIMMER(1)'));
assert.ok(man.includes('SYNOPSIS'));
assert.ok(man.includes('COMMANDS'));
console.log('  [PASS] Test 1: Standard UNIX man page layout verified');

// Test 2: Commands documented
assert.ok(man.includes('audit'));
assert.ok(man.includes('fix'));
assert.ok(man.includes('--backup'));
console.log('  [PASS] Test 2: Commands and options verified');

// Test 3: Exit status documented
assert.ok(man.includes('EXIT STATUS'));
assert.ok(man.includes('0       Success'));
console.log('  [PASS] Test 3: Exit codes documented');

console.log('ALL 3 MAN PAGE TESTS PASSED DETERMINISTICALLY!');
