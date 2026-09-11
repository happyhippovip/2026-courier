const { BFTShardSlashingEngine } = require('../lib/bft_shard_slashing_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Slashing Engine...');

const initialValidators = {
  val_alpha: 1000,
  val_beta: 1000,
  val_gamma: 1000,
  val_malicious: 1000
};

const engine = new BFTShardSlashingEngine(initialValidators);

// Test 1: Valid initial attestations
const att1 = {
  validatorId: 'val_alpha',
  shardId: 'shard_0',
  epoch: 10,
  blockHeight: 100,
  stateRoot: '0xabc123',
  signature: 'sig_a'
};
const res1 = engine.submitAttestation(att1);
assert(res1.accepted === true && res1.slashed === false);
console.log('✓ Test 1: Legitimate validator attestation accepted');

// Test 2: Equivocation detection & slashing
const attMaliciousA = {
  validatorId: 'val_malicious',
  shardId: 'shard_0',
  epoch: 10,
  blockHeight: 100,
  stateRoot: '0xroot_A',
  signature: 'sig_mal_1'
};
const attMaliciousB = {
  validatorId: 'val_malicious',
  shardId: 'shard_0',
  epoch: 10,
  blockHeight: 100,
  stateRoot: '0xroot_B_CONFLICT',
  signature: 'sig_mal_2'
};

const resMalA = engine.submitAttestation(attMaliciousA);
assert(resMalA.accepted === true);

// Submitting conflicting root for same height triggers immediate slashing
const resMalB = engine.submitAttestation(attMaliciousB);
assert(resMalB.slashed === true, 'Conflicting attestation must trigger slashing');
const malState = engine.getValidatorState('val_malicious');
assert.strictEqual(malState.status, 'EVICTED');
assert.strictEqual(malState.stake, 0);
assert.strictEqual(malState.slashedAmount, 1000);
console.log('✓ Test 2: Double-signing equivocation accurately slashed and validator evicted');

// Test 3: Rejected attestation from slashed validator
const attPostSlash = {
  validatorId: 'val_malicious',
  shardId: 'shard_0',
  epoch: 11,
  blockHeight: 101,
  stateRoot: '0xroot_C',
  signature: 'sig_mal_3'
};
const resPost = engine.submitAttestation(attPostSlash);
assert(resPost.accepted === false && resPost.reason === 'VALIDATOR_NOT_ACTIVE');
console.log('✓ Test 3: Evicted validator barred from subsequent round participation');

// Test 4: Cross-shard transfer quorum verification
const transferProof = {
  fromShard: 'shard_0',
  toShard: 'shard_1',
  txId: 'tx_98765',
  amount: 250,
  sender: 'agent_001',
  recipient: 'agent_002',
  sourceCommitment: '0xcomm_123',
  validatorSignatures: [
    { validatorId: 'val_alpha', signature: 's1' },
    { validatorId: 'val_beta', signature: 's2' },
    { validatorId: 'val_gamma', signature: 's3' }
  ]
};
const xferRes = engine.verifyCrossShardTransfer(transferProof);
assert(xferRes.valid === true);
assert(xferRes.quorumRatio >= 2/3);
console.log('✓ Test 4: Cross-shard 2f+1 BFT quorum transfer verified');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_BFT_SLASHING_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.totalBurnedStake, 1000);
assert.strictEqual(report.slashCount, 1);
console.log('✓ Test 5: Evidence report written to SAMPLE_BFT_SLASHING_REPORT.json');

console.log('All BFT Shard Slashing Engine tests passed successfully!');
