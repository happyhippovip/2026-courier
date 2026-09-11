const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BftShardRatchetEngine } = require('../lib/bft_shard_ratchet_engine');

console.log('Testing BFT Shard Finality Ratchet Consensus Engine...');
const engine = new BftShardRatchetEngine({ shardId: 'shard-alpha' });

// Test 1: Epoch 1 commit with valid 2f+1 signatures
const sigs1 = ['sig-node-1', 'sig-node-2', 'sig-node-3'];
const c1 = engine.proposeEpochTransition(1, '0xaaa111...', sigs1);
assert.strictEqual(c1.epoch, 1);
assert.strictEqual(c1.previousEpoch, 0);
console.log('✓ Test 1: Epoch 1 successfully committed with 2f+1 quorum (hash:', c1.commitmentHash.substring(0, 10), '...)');

// Test 2: Epoch 2 commit
const sigs2 = ['sig-node-1', 'sig-node-3', 'sig-node-4'];
const c2 = engine.proposeEpochTransition(2, '0xbbb222...', sigs2);
assert.strictEqual(c2.epoch, 2);
assert.strictEqual(c2.previousEpoch, 1);
console.log('✓ Test 2: Epoch 2 ratcheted forward monotonically (prev:', c2.previousEpoch, 'curr:', c2.epoch, ')');

// Test 3: Rollback rejection invariant
let caughtRollback = false;
try {
  engine.proposeEpochTransition(1, '0xinvalid...', sigs2);
} catch (err) {
  caughtRollback = true;
  console.log('✓ Test 3: Rollback attempt to Epoch 1 rejected fail-closed:', err.message);
}
assert.strictEqual(caughtRollback, true, 'Failed to reject rollback!');

// Test 4: Quorum deficit rejection
let caughtQuorum = false;
try {
  engine.proposeEpochTransition(3, '0xccc333...', ['sig-only-1']);
} catch (err) {
  caughtQuorum = true;
  console.log('✓ Test 4: Quorum deficit rejected fail-closed:', err.message);
}
assert.strictEqual(caughtQuorum, true, 'Failed to reject quorum deficit!');

const report = {
  test: 'BFT_SHARD_RATCHET_ENGINE',
  passed: true,
  highestEpoch: engine.highestCommittedEpoch,
  historyLength: engine.ratchetHistory.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_BFT_SHARD_RATCHET_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 5: Evidence report written to SAMPLE_BFT_SHARD_RATCHET_REPORT.json');
console.log('All BFT Shard Finality Ratchet Consensus tests passed successfully!');
