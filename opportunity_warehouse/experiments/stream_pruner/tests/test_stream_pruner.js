const assert = require('assert');
const { StreamPruner } = require('../lib/stream_pruner');

console.log('Testing StreamPruner...');

// Test 1: Chunk processing with newlines
const pruner = new StreamPruner();
const out1 = pruner.processChunk('Hello world!\nThis is line 2.\nIncom');
assert.strictEqual(out1, 'Hello world!\nThis is line 2.\n');
assert.strictEqual(pruner.buffer, 'Incom');

// Test 2: Flush final remaining buffer
const out2 = pruner.flush();
assert.strictEqual(out2, 'Incom');
assert.strictEqual(pruner.buffer, '');

// Test 3: Thinking tag stripping
const pruner2 = new StreamPruner({ stripThinking: true });
pruner2.processChunk('Action starting.\n<thought>Internal chain of thought reasoning...</thought>\nProceeding to answer.\n');
const flushed2 = pruner2.flush();
const allOut = pruner2.prunedChunks.join('');
assert.ok(!allOut.includes('chain of thought reasoning'));
assert.ok(allOut.includes('Action starting.'));
assert.ok(allOut.includes('Proceeding to answer.'));

// Test 4: Metrics calculation
const metrics = pruner2.getMetrics();
assert.ok(metrics.charsSaved > 0);
assert.ok(metrics.savingsPercent > 0);

console.log('All StreamPruner tests passed (4/4)!');
