/**
 * test_pre_commit_linter.js - Test suite for Pre-Commit Context Linter
 */
const assert = require('assert');
const { PreCommitContextLinter } = require('./lib/pre_commit_linter');

console.log('--- Running test_pre_commit_linter.js ---');

const linter = new PreCommitContextLinter({ maxTokensWarning: 500, maxTokensError: 1500 });

// Test 1: Clean file passes without issues
const cleanFile = {
  path: '.cursorrules',
  content: 'You are a TypeScript expert. Use strict type checking and functional style.'
};
const res1 = linter.lintAll([cleanFile]);
assert.strictEqual(res1.summary.passed, true, 'Clean file must pass');
assert.strictEqual(res1.summary.exitCode, 0, 'Exit code must be 0 for clean file');
console.log('✓ Test 1 Passed: Clean prompt file passes with 0 issues');

// Test 2: Detects secret leak and flags error
const dirtySecretFile = {
  path: 'prompts/system.md',
  content: 'Use OpenAI key: sk-abcdefghijklmnopqrstuvwxyz1234567890 to authenticate.'
};
const res2 = linter.lintAll([dirtySecretFile]);
assert.strictEqual(res2.summary.passed, false, 'Secret leak must fail linter');
assert.strictEqual(res2.summary.exitCode, 1, 'Exit code must be 1 on secret error');
assert.ok(res2.fileResults[0].issues.some(i => i.code === 'SECRET_LEAK_DETECTED'), 'Must report SECRET_LEAK_DETECTED');
console.log('✓ Test 2 Passed: API secret leak correctly detected and blocked');

// Test 3: Large file exceeds token budget
const largeText = 'A'.repeat(8000); // 2000 tokens > 1500 limit
const largeFile = { path: 'prompts/huge_context.txt', content: largeText };
const res3 = linter.lintAll([largeFile]);
assert.strictEqual(res3.summary.passed, false, 'Huge file must fail');
assert.ok(res3.fileResults[0].issues.some(i => i.code === 'TOKEN_BUDGET_EXCEEDED'), 'Must flag TOKEN_BUDGET_EXCEEDED');
console.log('✓ Test 3 Passed: Token budget overrun accurately flagged as error');

// Test 4: Autofix reduces bloat and collapses repetitive separators
const bloatedFile = {
  path: 'prompts/rules.md',
  content: 'Rule 1\n--------------------\n--------------------\n--------------------\nRule 2    \n'
};
const res4 = linter.lintAll([bloatedFile]);
assert.ok(res4.fileResults[0].tokensSavedIfFixed > 0, 'Autofix must save tokens');
assert.ok(!res4.fileResults[0].fixedContent.includes('--------------------\n--------------------'), 'Separators collapsed');
console.log('✓ Test 4 Passed: Autofix collapses duplicate banners and trims whitespace');

console.log('ALL 4 TESTS PASSED IN test_pre_commit_linter.js\n');
