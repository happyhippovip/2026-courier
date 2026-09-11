/**
 * test_state_checkpointer.js - Test suite for Context State Checkpointer
 */
const assert = require('assert');
const { ContextStateCheckpointer } = require('./lib/state_checkpointer');

console.log('--- Running test_state_checkpointer.js ---');

const checkpointer = new ContextStateCheckpointer();

// Test 1: Record sequential snapshots
const snap1 = checkpointer.recordSnapshot('agent_alpha', 'Initial state instructions', 1);
assert.strictEqual(snap1.snapshotId, 'SNAP_001');
assert.strictEqual(snap1.deltaCharCount, 0);

const snap2 = checkpointer.recordSnapshot('agent_alpha', 'Initial state instructions + turn 2 additions', 2);
assert.strictEqual(snap2.snapshotId, 'SNAP_002');
assert.ok(snap2.deltaCharCount > 0, 'Turn 2 delta must be positive');
console.log('✓ Test 1 Passed: Progressive snapshot recording with delta tracking');

// Test 2: Snapshot retrieval
const retrieved = checkpointer.getSnapshot('SNAP_001');
assert.ok(retrieved !== null);
assert.strictEqual(retrieved.content, 'Initial state instructions');
console.log('✓ Test 2 Passed: Accurate retrieval of historical snapshot by ID');

// Test 3: Rollback & state replay
const snap3 = checkpointer.recordSnapshot('agent_beta', 'Turn 3 branched state', 3);
assert.strictEqual(checkpointer.getLedgerSummary().totalSnapshots, 3);

const rollbackRes = checkpointer.replayTo('SNAP_002');
assert.strictEqual(rollbackRes.success, true);
assert.strictEqual(rollbackRes.restoredSnapshotId, 'SNAP_002');
assert.strictEqual(rollbackRes.removedSnapshotsCount, 1);
assert.strictEqual(checkpointer.getLedgerSummary().totalSnapshots, 2);
console.log('✓ Test 3 Passed: Replay and state rollback successfully pruned future branches');

// Test 4: Non-existent snapshot handling
const invalidReplay = checkpointer.replayTo('SNAP_999');
assert.strictEqual(invalidReplay.success, false);
assert.ok(invalidReplay.error.includes('Snapshot not found'));
console.log('✓ Test 4 Passed: Graceful error handling on invalid snapshot IDs');

console.log('ALL 4 TESTS PASSED IN test_state_checkpointer.js\n');
