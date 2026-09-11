const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTValidator, TendermintBFTCoordinator } = require('./lib/tendermint_bft_engine');

console.log('Testing Tendermint-Style BFT Consensus Engine...');

const validators = [
  new BFTValidator('val-1', 1),
  new BFTValidator('val-2', 1),
  new BFTValidator('val-3', 1),
  new BFTValidator('val-4', 1)
]; // Total power = 4, 2/3 threshold = 3

const coordinator = new TendermintBFTCoordinator(validators);

// Test 1: Successful unanimous consensus commit
const res1 = coordinator.executeConsensus(0, 'block-hash-1001');
assert.strictEqual(res1.status, 'CONSENSUS_COMMITTED');
assert.strictEqual(res1.prevotePower, 4);
assert.strictEqual(res1.precommitPower, 4);
assert.strictEqual(validators[0].state, 'COMMITTED');
assert.strictEqual(validators[0].lockedBlock, 'block-hash-1001');
console.log('✓ Test 1: Full 2-step consensus commit achieved with >2/3 quorum');

// Test 2: Lock preservation
assert.strictEqual(validators[1].lockedRound, 0);
assert.strictEqual(validators[1].lockedBlock, 'block-hash-1001');
console.log('✓ Test 2: Polka lock successfully held by validator nodes');

// Test 3: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 379,
  component: 'tendermint_bft_engine',
  validatorCount: validators.length,
  totalPower: coordinator.totalPower,
  twoThirdsThreshold: coordinator.twoThirdsThreshold,
  committedBlock: res1.block,
  polkaLockVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_TENDERMINT_BFT_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_TENDERMINT_BFT_REPORT.json');
console.log('All Tendermint BFT tests passed successfully!');
