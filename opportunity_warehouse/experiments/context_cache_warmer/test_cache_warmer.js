/**
 * test_cache_warmer.js - Test suite for Context Cache Warmer
 */
const assert = require('assert');
const { ContextCacheWarmer } = require('./lib/cache_warmer');

console.log('--- Running test_cache_warmer.js ---');

const warmer = new ContextCacheWarmer({ minCacheTokens: 500 }); // Low threshold for test fixture

// Test 1: Explicit boundary segmentation
const promptWithMarker = [
  'SYSTEM: You are an enterprise coding assistant.',
  'System rules: adhere to standard coding guidelines, zero regressions, fail-closed.',
  'Repository schema: table users, table orders, table products.',
  '--- DYNAMIC_USER_INPUT ---',
  'User: Fix the bug in auth.js'
].join('\n');

const res1 = warmer.segmentPrompt(promptWithMarker);
assert.strictEqual(res1.dynamicSuffix, 'User: Fix the bug in auth.js');
assert.ok(res1.staticPrefix.includes('System rules'));
console.log('✓ Test 1 Passed: Explicit boundary marker segmentation works accurately');

// Test 2: Cache eligibility threshold verification
const longStatic = 'Rule definition block for context caching.\n'.repeat(100); // ~4000 chars => ~1000 tokens
const fullPrompt = longStatic + '\n--- DYNAMIC_USER_INPUT ---\nTask: Run migration';
const res2 = warmer.segmentPrompt(fullPrompt);
assert.strictEqual(res2.cacheEligibility.isEligible, true, 'Static prefix > 500 tokens must be cache eligible');
assert.strictEqual(res2.cacheEligibility.deficitTokens, 0);
assert.ok(res2.economics.savingsPercentage > 50, 'Cache discount should yield >50% savings (got ' + res2.economics.savingsPercentage + '%)');
console.log('✓ Test 2 Passed: Cache eligibility detected with 90% discount calculation');

// Test 3: Deficit reporting on undersized prefix
const shortPrompt = 'Short system\n--- DYNAMIC_USER_INPUT ---\nShort user';
const res3 = warmer.segmentPrompt(shortPrompt);
assert.strictEqual(res3.cacheEligibility.isEligible, false);
assert.ok(res3.cacheEligibility.deficitTokens > 0, 'Must report token deficit for cache qualification');
assert.strictEqual(res3.economics.savingsPer1kRunsUSD, 0);
console.log('✓ Test 3 Passed: Undersized static prefix accurately reports cache deficit');

// Test 4: Automatic heuristic segmentation (without explicit marker)
const naturalPrompt = 'SYSTEM: Base knowledge instructions\nUser: Please refactor this component.';
const res4 = warmer.segmentPrompt(naturalPrompt);
assert.ok(res4.staticPrefix.startsWith('SYSTEM:'));
assert.ok(res4.dynamicSuffix.startsWith('User:'));
console.log('✓ Test 4 Passed: Heuristic regex separates static and dynamic user turns');

console.log('ALL 4 TESTS PASSED IN test_cache_warmer.js\n');
