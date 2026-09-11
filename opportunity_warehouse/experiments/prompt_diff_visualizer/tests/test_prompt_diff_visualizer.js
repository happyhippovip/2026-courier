const assert = require('assert');
const { computeLineDiff, renderDiffHtml } = require('../lib/diff_visualizer');

console.log('Running Prompt Diff Visualizer Tests...');

// Test 1: Exact match gives UNCHANGED
const diff1 = computeLineDiff('hello\nworld', 'hello\nworld');
assert.strictEqual(diff1.length, 2);
assert.strictEqual(diff1[0].type, 'UNCHANGED');
assert.strictEqual(diff1[1].type, 'UNCHANGED');
console.log('  [PASS] Test 1: Identical text diff verified');

// Test 2: Detect removed line
const orig = 'You are an expert engineer.\nAlways use TypeScript.\nNever apologize.';
const opt = 'Always use TypeScript.';
const diff2 = computeLineDiff(orig, opt);
const removed = diff2.filter(d => d.type === 'REMOVED');
assert.strictEqual(removed.length, 2);
assert.strictEqual(removed[0].text, 'You are an expert engineer.');
console.log('  [PASS] Test 2: Removed verbose preamble detected');

// Test 3: Detect added line
const diff3 = computeLineDiff('A', 'A\nB');
const added = diff3.filter(d => d.type === 'ADDED');
assert.strictEqual(added.length, 1);
assert.strictEqual(added[0].text, 'B');
console.log('  [PASS] Test 3: Added line detected');

// Test 4: Render HTML output
const html = renderDiffHtml(diff2, { title: 'Test Diff', tokenSavings: '-50%' });
assert.ok(html.includes('Test Diff'));
assert.ok(html.includes('-50%'));
assert.ok(html.includes('diff-container'));
console.log('  [PASS] Test 4: HTML diff document generated');

console.log('ALL 4 PROMPT DIFF TESTS PASSED DETERMINISTICALLY!');
