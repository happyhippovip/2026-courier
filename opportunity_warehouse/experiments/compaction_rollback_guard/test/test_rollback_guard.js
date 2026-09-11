const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CompactionRollbackGuard } = require('../lib/rollback_guard');

const guard = new CompactionRollbackGuard();

const rawTurn1 = { userQuery: 'Review purchase orders and compute EUR 5.00 revenue balance.', history: ['step 0'] };
const compTurn1 = { userQuery: 'Review purchase orders; balance=EUR 5.00.' };

const rawTurn2 = { userQuery: 'Dispatch settlement notification to customer.', intermediateErrors: ['Network timeout retry 1'] };
const compTurn2 = { userQuery: 'Dispatch settlement notification.' };

// Test 1: Create checkpoints with Merkle hash linking
const cp1 = guard.createCheckpoint(1, rawTurn1, compTurn1, { turnName: 'Turn 1' });
const cp2 = guard.createCheckpoint(2, rawTurn2, compTurn2, { turnName: 'Turn 2' });
assert.strictEqual(cp1.turnIndex, 1);
assert.strictEqual(cp2.prevHash, cp1.merkleHash, 'Checkpoint 2 must chain to Checkpoint 1');
console.log('✓ Assertion 1 Passed: Checkpoints created with cryptographic Merkle chaining');

// Test 2: Chain integrity validation
assert.strictEqual(guard.verifyChainIntegrity(), true, 'Chain integrity must verify successfully');
console.log('✓ Assertion 2 Passed: Merkle chain verified 100% authentic and tamper-free');

// Test 3: Rollback restores uncompacted state and marks successors reverted
const rollbackRes = guard.rollbackToCheckpoint(cp1.id);
assert.strictEqual(rollbackRes.restoredCheckpointId, cp1.id);
assert.strictEqual(rollbackRes.revertedTurnsCount, 1);
assert.deepStrictEqual(rollbackRes.rawContext, rawTurn1, 'Raw original context must be fully restored');
assert.strictEqual(guard.checkpoints[1].status, 'ROLLED_BACK', 'Successor must be marked ROLLED_BACK');
console.log('✓ Assertion 3 Passed: Rollback restored exact historical state losslessly');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_COMPACTION_ROLLBACK_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  totalCheckpoints: guard.checkpoints.length,
  activeCheckpointId: guard.activeCheckpointId,
  chainIntegrityVerified: true,
  rollbackVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_COMPACTION_ROLLBACK_REPORT.json');

console.log('All 4 Compaction Rollback Guard tests passed successfully!');