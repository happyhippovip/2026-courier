const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RadixPrefixRouter } = require('../lib/radix_router');

const router = new RadixPrefixRouter();

const sysPromptBase = 'SYSTEM: You are the Symphony Autonomous Commercial Agent. Standard rules apply.';
const sysPromptA = sysPromptBase + ' Mode: Financial Settlement.';
const sysPromptB = sysPromptBase + ' Mode: Context Trimmer Optimization.';

router.insert(sysPromptBase, { role: 'base' }, 'kv_block_base_001');
router.insert(sysPromptA, { role: 'settlement' }, 'kv_block_settlement_002');
router.insert(sysPromptB, { role: 'trimmer' }, 'kv_block_trimmer_003');

// Test 1: Exact prefix lookup and tree structure
const matchBase = router.findLongestPrefix(sysPromptBase);
assert.strictEqual(matchBase.matchedPrefix, sysPromptBase, 'Must match exact base prefix');
assert.ok(matchBase.cacheBlocks.includes('kv_block_base_001'), 'Must include base cache block');
console.log('✓ Test 1: Exact prefix match verified');

// Test 2: Subtree routing on live prompt
const livePrompt = sysPromptA + ' Command: verify order receipt for €5.00 euro.';
const routing = router.routePrompt(livePrompt);
assert.strictEqual(routing.reusableCacheBlocks.length, 2, 'Should match both base and mode A blocks');
assert.ok(routing.cacheReusePercentage > 50, 'Should reuse > 50% of prompt tokens from cache');
console.log('✓ Test 2: Subtree routing achieved ' + routing.cacheReusePercentage + '% KV-cache reuse');

// Test 3: Unmatched prompt yields minimal prefix
const foreignPrompt = 'USER: Unrelated query with zero system prompt.';
const foreignRouting = router.routePrompt(foreignPrompt);
assert.strictEqual(foreignRouting.matchedChars, 0, 'Unrelated prompt should match 0 chars');
assert.strictEqual(foreignRouting.reusableCacheBlocks.length, 0, 'No cache blocks reused');
console.log('✓ Test 3: Unmatched prompt correctly returns 0 cache reuse');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_RADIX_ROUTER_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  routerSummary: {
    totalEntries: router.totalEntries
  },
  sampleRouting: routing,
  unmatchedRouting: foreignRouting
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_RADIX_ROUTER_REPORT.json');

console.log('All Radix Prefix Router tests passed successfully!');
