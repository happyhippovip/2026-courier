const { BFTShardSnapshotAnchorEngine } = require('../lib/bft_shard_snapshot_anchor_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Snapshot Anchoring Consensus Engine...');

const validatorWeights = {
  node_0: 30,
  node_1: 30,
  node_2: 30,
  node_3: 10
};

const engine = new BFTShardSnapshotAnchorEngine(validatorWeights);

// Test 1: Ingest state across shards
engine.putShardState('shard_0', 10, 'account_a', 500);
engine.putShardState('shard_0', 12, 'account_b', 1200);
engine.putShardState('shard_1', 15, 'token_xyz', 9999);

const root0 = engine.computeShardStateRoot('shard_0');
const root1 = engine.computeShardStateRoot('shard_1');
assert(root0 && root0.length === 64);
assert(root1 && root1.length === 64);
console.log('✓ Test 1: Merkle state roots computed deterministically across shards');

// Test 2: Propose epoch anchor
const proposal = engine.proposeEpochAnchor(1);
assert.strictEqual(proposal.epoch, 1);
assert(proposal.anchorHash && proposal.anchorHash.length === 64);
assert.strictEqual(proposal.anchorPayload.shardRoots['shard_0'], root0);
console.log('✓ Test 2: Epoch anchor proposal created with cross-shard roots');

// Test 3: Sub-quorum rejection
const subQuorumSigs = [
  { validatorId: 'node_0', sig: 'sig_0' } // only 30% weight
];
const rejectRes = engine.certifyAnchor(proposal, subQuorumSigs);
assert.strictEqual(rejectRes.certified, false);
assert.strictEqual(rejectRes.reason, 'INSUFFICIENT_BFT_QUORUM');
console.log('✓ Test 3: Sub-quorum certification attempt rejected fail-closed');

// Test 4: Successful 2f+1 certification (90% weight)
const validSigs = [
  { validatorId: 'node_0', sig: 'sig_0' },
  { validatorId: 'node_1', sig: 'sig_1' },
  { validatorId: 'node_2', sig: 'sig_2' }
];
const certRes = engine.certifyAnchor(proposal, validSigs);
assert.strictEqual(certRes.certified, true);
assert.strictEqual(certRes.anchorRecord.epoch, 1);
assert.strictEqual(engine.lastCertifiedEpoch, 1);
console.log('✓ Test 4: 2f+1 BFT quorum certified epoch anchor successfully');

// Test 5: State compaction and historical log pruning
const pruneRes = engine.pruneHistoricalState('shard_0', 11);
assert.strictEqual(pruneRes.prunedCount, 1, 'account_a at height 10 should be pruned');
assert.strictEqual(pruneRes.remainingKeys, 1, 'account_b at height 12 should be retained');
console.log('✓ Test 5: Historical state safely pruned behind certified snapshot anchor');

// Test 6: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_SNAPSHOT_ANCHOR_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'bft_shard_snapshot_anchor_engine');
assert.strictEqual(report.lastCertifiedEpoch, 1);
console.log('✓ Test 6: Evidence report written to SAMPLE_SHARD_SNAPSHOT_ANCHOR_REPORT.json');

console.log('All BFT Shard Snapshot Anchoring Consensus Engine tests passed successfully!');
