const { BFTShardRollbackEngine } = require('../lib/bft_shard_rollback_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Rollback & Slashing Consensus Engine...');

const validators = {
  proposer_good: 2000,
  proposer_bad: 2000
};

const engine = new BFTShardRollbackEngine(validators);

// Test 1: Record legitimate blocks
engine.recordShardBlock('shard_0', 1, { balance_A: 100, balance_B: 200 }, 'proposer_good');
engine.recordShardBlock('shard_0', 2, { balance_A: 150, balance_B: 150 }, 'proposer_good');

const stateAt2 = engine.getCurrentShardState('shard_0');
assert.strictEqual(stateAt2.get('balance_A'), 150);
console.log('✓ Test 1: Legitimate shard state transitions recorded');

// Test 2: Malicious block proposed at height 3
engine.recordShardBlock('shard_0', 3, { balance_A: 999999, balance_B: 150 }, 'proposer_bad');
const stateAt3 = engine.getCurrentShardState('shard_0');
assert.strictEqual(stateAt3.get('balance_A'), 999999);
console.log('✓ Test 2: Compromised block recorded on shard');

// Test 3: Submit fraud proof and execute atomic rollback
const fraudProof = {
  shardId: 'shard_0',
  invalidHeight: 3,
  proposerId: 'proposer_bad',
  reason: 'DOUBLE_SPEND_INFLATION_VIOLATION'
};
const res = engine.submitFraudProof(fraudProof);
assert.strictEqual(res.success, true);
assert.strictEqual(res.slashed, true);
assert.strictEqual(res.rollbackRecord.restoredHeight, 2);

// Verify state rolled back cleanly to height 2
const statePostRollback = engine.getCurrentShardState('shard_0');
assert.strictEqual(statePostRollback.get('balance_A'), 150, 'State must revert to height 2 value');

// Verify malicious proposer slashed and evicted
const badVal = engine.validators.get('proposer_bad');
assert.strictEqual(badVal.status, 'EVICTED');
assert.strictEqual(badVal.stake, 0);
console.log('✓ Test 3: Fraud proof executed atomic rollback and proposer slashing');

// Test 4: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_ROLLBACK_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'bft_shard_rollback_engine');
assert.strictEqual(report.rollbackCount, 1);
console.log('✓ Test 4: Evidence report written to SAMPLE_SHARD_ROLLBACK_REPORT.json');

console.log('All BFT Shard Rollback & Slashing Consensus Engine tests passed successfully!');
