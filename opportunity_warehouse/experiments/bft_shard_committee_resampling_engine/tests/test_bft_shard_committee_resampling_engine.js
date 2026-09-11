const { BFTShardCommitteeReSamplingEngine } = require('../lib/bft_shard_committee_resampling_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Committee Re-Sampling Consensus Engine...');

const validatorPool = ['val_0', 'val_1', 'val_2', 'val_3', 'val_4', 'val_5'];
const engine = new BFTShardCommitteeReSamplingEngine(validatorPool, 3);

// Test 1: Derive non-biasable epoch seed
const seed1 = engine.deriveEpochSeed(1, 'initial_genesis_entropy');
const seed2 = engine.deriveEpochSeed(2, seed1);
assert(seed1 && seed1.length === 64);
assert(seed2 && seed2.length === 64);
assert.notStrictEqual(seed1, seed2);
console.log('✓ Test 1: Deterministic epoch VRF seeds derived');

// Test 2: Sample committee for shard_0 at epoch 1
const proposal = engine.sampleCommittee('shard_0', 1, seed1);
assert.strictEqual(proposal.shardId, 'shard_0');
assert.strictEqual(proposal.committee.length, 3);
console.log('✓ Test 2: Committee of 3 validators sampled: ' + JSON.stringify(proposal.committee));

// Test 3: Sub-quorum handover rejection
const subQuorumSigs = [
  { validatorId: 'val_0', sig: 's0' } // 1 of 3 (< 67%)
];
const rejectRes = engine.certifyHandover(proposal, subQuorumSigs);
assert.strictEqual(rejectRes.certified, false);
assert.strictEqual(rejectRes.reason, 'INSUFFICIENT_BFT_COMMITTEE_QUORUM');
console.log('✓ Test 3: Sub-quorum committee handover rejected fail-closed');

// Test 4: 2f+1 BFT quorum certification (2 of 3 >= 67%)
const validSigs = [
  { validatorId: 'val_0', sig: 's0' },
  { validatorId: 'val_1', sig: 's1' }
];
const certRes = engine.certifyHandover(proposal, validSigs);
assert.strictEqual(certRes.certified, true);
assert.deepStrictEqual(engine.getActiveCommittee('shard_0'), proposal.committee);
console.log('✓ Test 4: 2f+1 BFT quorum certified committee handover to Epoch 1');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_COMMITTEE_RESAMPLING_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'bft_shard_committee_resampling_engine');
assert.strictEqual(report.transitionCount, 1);
console.log('✓ Test 5: Evidence report written to SAMPLE_SHARD_COMMITTEE_RESAMPLING_REPORT.json');

console.log('All BFT Shard Committee Re-Sampling Consensus Engine tests passed successfully!');
