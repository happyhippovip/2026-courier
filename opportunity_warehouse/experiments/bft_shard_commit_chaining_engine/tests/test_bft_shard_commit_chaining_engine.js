const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTShardCommitChainingEngine } = require('../lib/bft_shard_commit_chaining_engine');

console.log('Testing BFT Shard Commit-Proof Chaining Consensus Engine...');

const engineShardA = new BFTShardCommitChainingEngine('shard_A', 3);

// Test 1: Generate certified Commit Proof for Shard A
const payloadA = require('crypto').createHash('sha256').update(JSON.stringify({
  shardId: 'shard_A',
  blockNumber: 10,
  stateRoot: '0xroota123'
})).digest('hex');

const sigsA = [
  { nodeId: 'node_0', signature: require('crypto').createHash('sha256').update('node_0:' + payloadA).digest('hex') },
  { nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + payloadA).digest('hex') },
  { nodeId: 'node_2', signature: require('crypto').createHash('sha256').update('node_2:' + payloadA).digest('hex') }
];

const cpResult = engineShardA.generateCommitProof(10, '0xroota123', sigsA);
assert.strictEqual(cpResult.verified, true);
const cpHash = cpResult.proof.proofHash;
console.log('✓ Test 1: Commit Proof for Shard A successfully certified with 3 signatures');

// Test 2: Cross-shard block chaining referencing parent proof
const chainedBlock = engineShardA.proposeChainedCrossShardBlock(11, {
  fromShard: 'shard_A',
  toShard: 'shard_B',
  value: 500
}, cpHash);

assert.strictEqual(chainedBlock.parentProofHash, cpHash);
assert.strictEqual(chainedBlock.parentBlockNumber, 10);
console.log('✓ Test 2: Cross-shard block successfully chained to validated parent commit proof');

// Test 3: Unverified proof rejected fail-closed
assert.throws(() => {
  engineShardA.proposeChainedCrossShardBlock(12, { value: 100 }, '0xunverifiedhash');
}, /Invalid parent commit proof/);
console.log('✓ Test 3: Unverified or non-existent commit proof rejected fail-closed');

// Test 4: Verify chain integrity
assert.strictEqual(engineShardA.verifyChainIntegrity(), true);
console.log('✓ Test 4: Full causal commit chain integrity validated');

// Test 5: Export evidence report
const evidenceReport = {
  experiment: 'bft_shard_commit_chaining_engine',
  timestamp: new Date().toISOString(),
  shardId: engineShardA.shardId,
  certifiedCommitProofs: engineShardA.commitProofs.size,
  chainedBlocksCount: engineShardA.chainedBlocks.length,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_COMMIT_CHAINING_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 5: Evidence report written to SAMPLE_SHARD_COMMIT_CHAINING_REPORT.json');

console.log('All BFT Shard Commit-Proof Chaining Engine tests passed successfully!');
