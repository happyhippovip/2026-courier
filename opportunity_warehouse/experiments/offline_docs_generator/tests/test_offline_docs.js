const assert = require('assert');
const { generateDocsHtml } = require('../lib/docs_compiler');

console.log('Running Offline Docs Compiler Tests...');

// Test 1: Basic compilation
const html = generateDocsHtml({ version: 'v1.0.0' });
assert.ok(html.includes('Agent Context Trimmer'), 'Must contain title');
assert.ok(html.includes('v1.0.0 Production'), 'Must contain version badge');
assert.ok(html.includes('searchInput'), 'Must include interactive search filter script');
console.log('  [PASS] Test 1: HTML generation validated');

// Test 2: CLI reference inclusion
assert.ok(html.includes('CLI Reference'), 'Must document CLI commands');
assert.ok(html.includes('--backup'), 'Must document backup flag');
console.log('  [PASS] Test 2: CLI reference content verified');

// Test 3: Standalone zero-dependency styling
assert.ok(html.includes('<style>'), 'Must contain inline CSS');
assert.ok(html.includes('SFMono-Regular'), 'Must contain monospaced font declarations');
console.log('  [PASS] Test 3: Standalone styles confirmed');

console.log('ALL 3 OFFLINE DOCS TESTS PASSED DETERMINISTICALLY!');
