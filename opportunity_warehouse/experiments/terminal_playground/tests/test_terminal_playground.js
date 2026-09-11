const assert = require('assert');
const { TerminalPlayground } = require('../lib/terminal_playground');

console.log('Testing TerminalPlayground...');

const sample = '# Header 1\n<!-- Comment -->\n# Header 1\n\n\n\nCode line\n══════ Decorative ══════';
const playground = new TerminalPlayground(sample);

// Test 1: Full pruning enabled
const r1 = playground.simulatePruning();
assert.ok(r1.tokensSaved > 0);
assert.ok(!r1.previewSnippet.includes('Comment'));
assert.ok(!r1.previewSnippet.includes('══'));

// Test 2: Toggle rule off
playground.toggleRule('stripDecorativeAscii');
assert.strictEqual(playground.activeRules.stripDecorativeAscii, false);
const r2 = playground.simulatePruning();
assert.ok(r2.finalTokens >= r1.finalTokens);

// Test 3: Toggle rule on
playground.toggleRule('stripDecorativeAscii');
assert.strictEqual(playground.activeRules.stripDecorativeAscii, true);

// Test 4: Deduplicate repeated headers
assert.ok(r1.previewSnippet.includes('Header 1'));
const headerMatches = (r1.previewSnippet.match(/# Header 1/g) || []).length;
assert.strictEqual(headerMatches, 1);

console.log('All TerminalPlayground tests passed (4/4)!');
