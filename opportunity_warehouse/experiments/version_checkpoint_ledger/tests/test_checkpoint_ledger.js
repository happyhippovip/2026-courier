const assert = require('assert');
const { CheckpointLedger } = require('../lib/checkpoint_ledger');

console.log('Testing CheckpointLedger...');

const ledger = new CheckpointLedger();

// Test 1: Record run
const run1 = ledger.recordRun({
  runId: 'RUN-001',
  originalText: 'Original text 100 bytes long '.repeat(4),
  trimmedText: 'Original text 100 bytes long',
  metadata: { agent: 'architect' }
});
assert.strictEqual(run1.runId, 'RUN-001');
assert.ok(run1.bytesSaved > 0);
assert.strictEqual(typeof run1.originalHash, 'string');
assert.strictEqual(run1.originalHash.length, 64);

// Test 2: Find by runId
const found = ledger.findByRunId('RUN-001');
assert.strictEqual(found.runId, 'RUN-001');
assert.strictEqual(found.metadata.agent, 'architect');

// Test 3: Find non-existent runId
assert.strictEqual(ledger.findByRunId('UNKNOWN'), null);

// Test 4: Summary calculation
ledger.recordRun({
  runId: 'RUN-002',
  originalText: 'Another prompt',
  trimmedText: 'Another prompt'
});
const summary = ledger.getSummary();
assert.strictEqual(summary.totalRuns, 2);
assert.ok(summary.totalBytesSaved > 0);

console.log('All CheckpointLedger tests passed (4/4)!');
