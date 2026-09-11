const assert = require('assert');
const { estimateTokens, parseSections, analyzeContextBudget } = require('../lib/budget_allocator');

console.log('Running Context Budget Allocator Tests...');

// Test 1: Token estimation
const text = 'This is a sample sentence for tokenization tests.';
const tokens = estimateTokens(text);
assert.ok(tokens > 5 && tokens < 20, 'Token estimation should be ~text.length/4');
console.log('  [PASS] Test 1: Token estimation validated');

// Test 2: Section parsing
const markdown = `
# Architecture
Use clean architecture.
# Testing
Write unit tests for all functions.
`;
const secs = parseSections(markdown);
assert.strictEqual(secs.length, 2);
assert.strictEqual(secs[0].title, 'Architecture');
assert.strictEqual(secs[1].title, 'Testing');
console.log('  [PASS] Test 2: Markdown section parsing verified');

// Test 3: Budget analysis within limits
const sampleContent = '# Guidelines\nShort rules\n# Notes\nBe concise.';
const budgetOk = analyzeContextBudget(sampleContent, { totalContextWindow: 32000 });
assert.strictEqual(budgetOk.is_over_budget, false);
assert.ok(budgetOk.headroom_tokens > 0);
console.log('  [PASS] Test 3: Safe context budget analysis confirmed');

// Test 4: Over budget detection
const largeContent = 'a'.repeat(4000); // ~1000 tokens
const budgetOver = analyzeContextBudget(largeContent, { totalContextWindow: 4000, maxBudgetRatio: 0.10 }); // max 400 tokens
assert.strictEqual(budgetOver.is_over_budget, true);
assert.ok(budgetOver.headroom_tokens < 0);
console.log('  [PASS] Test 4: Over-budget threshold detection verified');

console.log('ALL 4 CONTEXT BUDGET TESTS PASSED DETERMINISTICALLY!');
