const assert = require('assert');
const { mergeAgentContexts } = require('../lib/context_merger');

console.log('Running Cross-Agent Context Merger Tests...');

// Test 1: Empty input handling
const emptyRes = mergeAgentContexts({});
assert.strictEqual(emptyRes.total_savings_tokens, 0);
console.log('  [PASS] Test 1: Empty input handled');

// Test 2: Multi-agent prompt deduplication
const agents = {
  coder: 'Always write TypeScript strict.\nUse functional purity.\nWrite unit tests.\nFocus on logic implementation.',
  tester: 'Always write TypeScript strict.\nUse functional purity.\nWrite unit tests.\nFocus on test assertions.',
  reviewer: 'Always write TypeScript strict.\nUse functional purity.\nWrite unit tests.\nFocus on code style and security.'
};

const mergeRes = mergeAgentContexts(agents);
assert.strictEqual(mergeRes.agents_count, 3);
assert.strictEqual(mergeRes.shared_rules_lines_count, 3);
assert.ok(mergeRes.shared_base_rules.includes('Always write TypeScript strict.'));
assert.ok(mergeRes.agent_overlays.coder.includes('Focus on logic implementation.'));
assert.ok(mergeRes.metrics.tokens_saved_per_round > 0);
console.log('  [PASS] Test 2: Shared rules factored out into base layer');

// Test 3: Completely disjoint prompts
const disjoint = {
  agentA: 'Apples are red.\nBananas are yellow.',
  agentB: 'Carrots are orange.\nSpinach is green.'
};
const disjointRes = mergeAgentContexts(disjoint);
assert.strictEqual(disjointRes.shared_rules_lines_count, 0);
assert.strictEqual(disjointRes.shared_base_rules, '');
console.log('  [PASS] Test 3: Disjoint agent instructions correctly kept in overlays');

// Test 4: Single agent identity
const single = { bot: 'Rule 1\nRule 2' };
const singleRes = mergeAgentContexts(single);
assert.strictEqual(singleRes.shared_rules_lines_count, 2);
assert.strictEqual(singleRes.agent_overlays.bot, '');
console.log('  [PASS] Test 4: Single agent identity handled');

console.log('ALL 4 CONTEXT MERGER TESTS PASSED DETERMINISTICALLY!');
