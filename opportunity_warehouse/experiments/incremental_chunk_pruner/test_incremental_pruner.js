/**
 * test_incremental_pruner.js - Test suite for Incremental Chunk Pruner
 */
const assert = require('assert');
const { IncrementalChunkPruner } = require('./lib/incremental_pruner');

console.log('--- Running test_incremental_pruner.js ---');

const pruner = new IncrementalChunkPruner({ maxChunkChars: 40 });

// Test 1: Chunk splitting across double newline boundaries
const sampleText = 'Section 1: Setup\n\nSection 2: Database Configuration\n\nSection 3: Routes & Controllers';
const chunks = pruner.splitIntoChunks(sampleText);
assert.ok(chunks.length >= 2, 'Should divide text into multiple chunks');
console.log('✓ Test 1 Passed: Text correctly divided across semantic boundaries into ' + chunks.length + ' chunks');

// Test 2: Chunk pruning removes debug comments
const dirtyChunk = 'function test() {\n// DEBUG: variable trace\nreturn 1;\n}';
const cleaned = pruner.pruneChunk(dirtyChunk);
assert.ok(!cleaned.includes('DEBUG:'), 'Debug comments must be stripped');
assert.ok(cleaned.includes('return 1;'), 'Return statement must be preserved');
console.log('✓ Test 2 Passed: Single chunk pruning preserves code and strips noise');

// Test 3: Full stream processing with seamless assembly
const streamInput = [
  'Module A: Authentication\n// DEBUG: trace\nfunction auth() { return true; }',
  'Module B: Database\n// DEBUG: trace\nfunction db() { return "connected"; }',
  'Module C: Analytics\n// DEBUG: trace\nfunction track() { return 100; }'
].join('\n\n');

const res = pruner.processStream(streamInput);
assert.strictEqual(res.chunksProcessed, 3, 'Must process exactly 3 chunks');
assert.ok(res.totalSavedChars > 0, 'Must save characters');
assert.ok(!res.output.includes('DEBUG:'), 'Output must be fully cleaned');
assert.ok(res.output.includes('Module A') && res.output.includes('Module C'), 'All modules present in assembled output');
console.log('✓ Test 3 Passed: Stream processing cleans and reassembles stream seamlessly');

// Test 4: Single chunk passthrough when smaller than limit
const tinyPruner = new IncrementalChunkPruner({ maxChunkChars: 1000 });
const tinyText = 'Short prompt.';
const tinyRes = tinyPruner.processStream(tinyText);
assert.strictEqual(tinyRes.chunksProcessed, 1, 'Small input should yield 1 chunk');
assert.strictEqual(tinyRes.output, 'Short prompt.');
console.log('✓ Test 4 Passed: Short input handled as single chunk without overhead');

console.log('ALL 4 TESTS PASSED IN test_incremental_pruner.js\n');
