const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { KvCacheWarmupOptimizer } = require('../lib/cache_warmup_optimizer');

const optimizer = new KvCacheWarmupOptimizer();

const basePrompt = [
  'You are Antigravity Enterprise Autonomous Agent v2.5.',
  'Follow all enterprise security rules, KMS key encryption standards, and fail-closed safety constraints.',
  'Available tools: [read_db, write_audit_log, dispatch_webhook].',
  '--- DYNAMIC_CONTEXT ---',
  'Turn 1: User asked to check revenue status at timestamp 2026-09-11T12:00:00Z.'
].join('\n');

const turn2Prompt = [
  'You are Antigravity Enterprise Autonomous Agent v2.5.  ',
  'Follow all enterprise security rules, KMS key encryption standards, and fail-closed safety constraints.',
  'Available tools: [read_db, write_audit_log, dispatch_webhook].',
  '--- DYNAMIC_CONTEXT ---',
  'Turn 2: User asked to poll pending invoices at timestamp 2026-09-11T12:05:00Z.'
].join('\n');

// Test 1: Partition prompt into static prefix and dynamic tail
const part1 = optimizer.partitionPrompt(basePrompt);
assert.ok(part1.staticPrefix.includes('Available tools:'), 'Static prefix must contain tools');
assert.ok(part1.dynamicTail.includes('Turn 1'), 'Dynamic tail must isolate turn 1 context');
assert.ok(part1.cachableRatio > 0.60, 'Static prefix must constitute >60% of total tokens');
console.log('✓ Assertion 1 Passed: Prompt cleanly partitioned with ' + (part1.cachableRatio * 100).toFixed(1) + '% cachable ratio');

// Test 2: Canonicalization eliminates formatting jitter across turns
const part2 = optimizer.partitionPrompt(turn2Prompt);
assert.strictEqual(part1.staticPrefix, part2.staticPrefix, 'Canonicalized static prefixes must match identically');
console.log('✓ Assertion 2 Passed: Canonicalization achieved 100% prefix equality despite whitespace differences');

// Test 3: Evaluate cache hit metrics
const hitMetrics = optimizer.evaluateCacheHitMetrics(part1.staticPrefix, part2.staticPrefix);
assert.strictEqual(hitMetrics.isExactPrefixMatch, true, 'Must be an exact prefix match');
assert.strictEqual(hitMetrics.cacheHitRate, 1.0, 'Cache hit rate on static prefix must be 100%');
assert.ok(hitMetrics.latencyReductionPercent >= 80, 'Prefill latency reduction should be >=80%');
console.log('✓ Assertion 3 Passed: Cache hit metrics evaluated (100% hit rate, ' + hitMetrics.latencyReductionPercent + '% latency drop)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_KV_CACHE_OPTIMIZATION_REPORT.json');
const evidenceReport = {
  timestamp: new Date().toISOString(),
  partitionMetrics: part1,
  hitMetrics,
  cacheStabilityAttested: true
};
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_KV_CACHE_OPTIMIZATION_REPORT.json');

console.log('All 4 KV Cache Warmup Optimizer tests passed successfully!');