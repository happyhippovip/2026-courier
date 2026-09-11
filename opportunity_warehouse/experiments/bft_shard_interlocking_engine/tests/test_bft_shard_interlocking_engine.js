const { BFTShardInterlockingEngine } = require('../lib/bft_shard_interlocking_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Checkpoint Interlocking Consensus Engine...');

const validators = {
  val_A: 40,
  val_B: 30,
  val_C: 30
};

const engine = new BFTShardInterlockingEngine(validators);

// Test 1: Register peer checkpoints for Shard 1 and Shard 2
const cp1 = engine.registerShardCheckpoint('shard_1', 10, '0xroot_shard_1_ep10');
const cp2 = engine.registerShardCheckpoint('shard_2', 12, '0xroot_shard_2_ep12');
assert.strictEqual(engine.shardCheckpoints.size, 2);
console.log('✓ Test 1: Peer shard checkpoints registered');

// Test 2: Construct interlocked block proposal on Shard 0
const proposal = engine.proposeInterlockedBlock('shard_0', 100, ['tx_alpha', 'tx_beta']);
assert.strictEqual(proposal.shardId, 'shard_0');
assert.strictEqual(proposal.payload.peerRoots['shard_1'].root, '0xroot_shard_1_ep10');
assert.strictEqual(proposal.payload.peerRoots['shard_2'].root, '0xroot_shard_2_ep12');
console.log('✓ Test 2: Interlocked block proposal embeds peer shard roots');

// Test 3: Sub-quorum rejection
const subSigs = [{ validatorId: 'val_B', sig: 'sig_b' }]; // 30% (< 67%)
const subRes = engine.certifyInterlockedBlock(proposal, subSigs);
assert.strictEqual(subRes.certified, false);
assert.strictEqual(subRes.reason, 'INSUFFICIENT_BFT_QUORUM');
console.log('✓ Test 3: Sub-quorum interlocking proposal rejected fail-closed');

// Test 4: 2f+1 BFT certification (70% weight)
const validSigs = [
  { validatorId: 'val_A', sig: 'sig_a' },
  { validatorId: 'val_B', sig: 'sig_b' }
];
const certRes = engine.certifyInterlockedBlock(proposal, validSigs);
assert.strictEqual(certRes.certified, true);
assert.strictEqual(engine.interlockedBlocks.length, 1);
console.log('✓ Test 4: 2f+1 BFT quorum certified interlocked block');

// Test 5: Verify causal interlock
const verifyRes = engine.verifyCausalInterlock(proposal.blockHash, 'shard_1', '0xroot_shard_1_ep10');
assert.strictEqual(verifyRes.valid, true);
assert.strictEqual(verifyRes.matches, true);
console.log('✓ Test 5: Causal interlock cryptographically validated against Shard 1 root');

// Test 6: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_INTERLOCKING_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'bft_shard_interlocking_engine');
assert.strictEqual(report.interlockedBlockCount, 1);
console.log('✓ Test 6: Evidence report written to SAMPLE_SHARD_INTERLOCKING_REPORT.json');

console.log('All BFT Shard Checkpoint Interlocking Consensus Engine tests passed successfully!');
