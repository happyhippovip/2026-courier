const { BFTShardHorizonCompactionEngine } = require('../lib/bft_shard_horizon_compaction_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Horizon Compaction Consensus Engine...');

const validators = {
  val_1: 35,
  val_2: 35,
  val_3: 30
};

const engine = new BFTShardHorizonCompactionEngine(validators, 2);

// Test 1: Record states across multiple epochs
engine.recordEpochState(1, { account_A: 100, account_B: 200 });
engine.recordEpochState(2, { account_A: 120, account_B: 180 });
engine.recordEpochState(3, { account_A: 150, account_B: 150 });
engine.recordEpochState(4, { account_A: 170, account_B: 130 });

assert.strictEqual(engine.currentEpoch, 4);
const horizonEp = engine.getFinalityHorizonEpoch(); // 4 - 2 = 2
assert.strictEqual(horizonEp, 2);
console.log('✓ Test 1: Epoch progression and horizon calculation verified (Horizon: ' + horizonEp + ')');

// Test 2: Propose compaction at horizon epoch 2
const proposal = engine.proposeCompaction(horizonEp);
assert.strictEqual(proposal.targetEpoch, 2);
assert(proposal.stateRoot && proposal.stateRoot.length === 64);
console.log('✓ Test 2: Compaction proposal created at horizon boundary');

// Test 3: Sub-quorum rejection
const subQuorum = [{ validatorId: 'val_3', sig: 's3' }]; // 30% weight (< 67%)
const subRes = engine.certifyCompaction(proposal, subQuorum);
assert.strictEqual(subRes.certified, false);
assert.strictEqual(subRes.reason, 'INSUFFICIENT_BFT_QUORUM');
console.log('✓ Test 3: Sub-quorum compaction attempt rejected fail-closed');

// Test 4: 2f+1 BFT certification (70% weight)
const validSigs = [
  { validatorId: 'val_1', sig: 's1' },
  { validatorId: 'val_2', sig: 's2' }
];
const certRes = engine.certifyCompaction(proposal, validSigs);
assert.strictEqual(certRes.certified, true);
assert.strictEqual(engine.getEpochStatus(2), 'FINALIZED');
assert.strictEqual(engine.getEpochStatus(1), 'PRUNED');
console.log('✓ Test 4: 2f+1 BFT quorum certified horizon: epoch 2 finalized, epoch 1 pruned');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_HORIZON_COMPACTION_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'bft_shard_horizon_compaction_engine');
assert.strictEqual(report.compactedCount, 1);
console.log('✓ Test 5: Evidence report written to SAMPLE_SHARD_HORIZON_COMPACTION_REPORT.json');

console.log('All BFT Shard Horizon Compaction Consensus Engine tests passed successfully!');
