const assert = require('assert');
const { PromptCacheOptimizer } = require('../lib/cache_optimizer');

console.log('Testing PromptCacheOptimizer...');

const optimizer = new PromptCacheOptimizer({ minCachePrefixTokens: 500 });

// Test 1: Partition with explicit dynamic marker
const staticPart = 'System Instructions: Follow all safety protocols. '.repeat(60); // ~2800 chars -> ~700 tokens
const dynamicPart = 'User request for today: build a website.';
const fullPrompt = staticPart + '\n## Current Session\n' + dynamicPart;

const partitioned = optimizer.partitionPrompt(fullPrompt);
assert.strictEqual(partitioned.cacheEligible, true);
assert.strictEqual(partitioned.anthropicPayload.cache_control.type, 'ephemeral');
assert.ok(partitioned.staticPrefix.includes('Follow all safety protocols'));
assert.ok(partitioned.dynamicSuffix.includes('build a website'));
assert.strictEqual(typeof partitioned.prefixHash, 'string');

// Test 2: Fallback split when no marker present
const plainPrompt = 'A'.repeat(3000);
const part2 = optimizer.partitionPrompt(plainPrompt);
assert.ok(part2.staticPrefix.length > 0);
assert.ok(part2.dynamicSuffix.length > 0);

// Test 3: Short prompt not cache eligible
const shortPrompt = 'Short prompt under min tokens';
const part3 = optimizer.partitionPrompt(shortPrompt);
assert.strictEqual(part3.cacheEligible, false);
assert.strictEqual(part3.anthropicPayload.cache_control, null);

// Test 4: Empty prompt handling
const part4 = optimizer.partitionPrompt('');
assert.strictEqual(part4.cacheEligible, false);

console.log('All PromptCacheOptimizer tests passed (4/4)!');
