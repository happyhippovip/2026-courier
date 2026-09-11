/**
 * test_compaction_engine.js - Test suite for Context Compaction Engine
 */
const assert = require('assert');
const { ContextCompactionEngine } = require('./lib/compaction_engine');

console.log('--- Running test_compaction_engine.js ---');

const engine = new ContextCompactionEngine();

// Test 1: Compacting repetitive error traces
const sampleTrace = 'Error: Connection timeout\n    at Socket.onTimeout (net.js:100:10)\n    at processTimers (timers.js:500:20)';
const messyPrompt = [
  'Task: Process payments',
  sampleTrace,
  'Attempting retry #1...',
  sampleTrace,
  'Attempting retry #2...',
  sampleTrace,
  'Status: Failed after retries'
].join('\n');

const res1 = engine.compactContext(messyPrompt);
assert.strictEqual(res1.coalescedTracesCount, 2, 'Should coalesce 2 redundant error traces');
assert.ok(res1.tokensSaved > 0, 'Compacted tokens must be fewer than original tokens');
assert.ok(res1.compactedText.includes('[COALESCED_ERROR_TRACE: TRACE_1'), 'Must include trace reference marker');
console.log('✓ Test 1 Passed: Redundant error traces successfully coalesced into compact reference');

// Test 2: Fragmentation index calculation
const highFragText = [
  'const duplicateBlockA = "Some long redundant string that repeats many times";',
  'const duplicateBlockA = "Some long redundant string that repeats many times";',
  'const duplicateBlockA = "Some long redundant string that repeats many times";',
  'const duplicateBlockA = "Some long redundant string that repeats many times";'
].join('\n');
const frag = engine.calculateFragmentationIndex(highFragText);
assert.ok(frag > 0.5, 'Fragmentation index should be > 0.5 for highly repetitive text (got ' + frag + ')');
console.log('✓ Test 2 Passed: Fragmentation index detects high repetition accurately (' + frag + ')');

// Test 3: Idempotency (compacting already compacted text does not mutate or bloat)
const resOnce = engine.compactContext(messyPrompt);
const resTwice = engine.compactContext(resOnce.compactedText);
assert.strictEqual(resOnce.compactedText, resTwice.compactedText, 'Compaction must be completely idempotent');
console.log('✓ Test 3 Passed: Compaction process is 100% idempotent');

// Test 4: Clean prompt handling
const cleanPrompt = 'System: You are an autonomous coding assistant.\nInstruction: Implement feature X.';
const cleanRes = engine.compactContext(cleanPrompt);
assert.strictEqual(cleanRes.coalescedTracesCount, 0, 'Clean prompt has 0 coalesced traces');
assert.strictEqual(cleanRes.tokensSaved, 0, 'No token savings on already minimal prompt');
console.log('✓ Test 4 Passed: Clean prompts pass through without unintended alterations');

console.log('ALL 4 TESTS PASSED IN test_compaction_engine.js\n');
