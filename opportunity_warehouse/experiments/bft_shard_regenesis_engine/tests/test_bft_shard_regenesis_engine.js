const { BFTShardReGenesisEngine } = require('../lib/bft_shard_regenesis_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Re-Genesis Consensus Engine...');

const validators = {
  v_0: 40,
  v_1: 30,
  v_2: 30
};

const engine = new BFTShardReGenesisEngine(validators);

// Test 1: Populate state and historical blocks
engine.setAccountBalance('agent_alpha', 5000);
engine.setAccountBalance('agent_beta', 3500);
engine.recordBlock(1, ['tx_1', 'tx_2']);
engine.recordBlock(2, ['tx_3']);
engine.recordBlock(3, ['tx_4', 'tx_5']);

assert.strictEqual(engine.historicalBlocks.length, 3);
console.log('✓ Test 1: Initial state and historical blocks populated');

// Test 2: Propose Re-Genesis at Epoch 1
const proposal = engine.proposeReGenesis(1);
assert.strictEqual(proposal.targetEpoch, 1);
assert.strictEqual(proposal.purgedBlockCount, 3);
assert(proposal.genesisRoot && proposal.genesisRoot.length === 64);
console.log('✓ Test 2: Re-Genesis proposal computed with deterministic state root');

// Test 3: Sub-quorum rejection
const subQuorum = [{ validatorId: 'v_0', sig: 's0' }]; // 40% weight (< 67%)
const subRes = engine.certifyReGenesis(proposal, subQuorum);
assert.strictEqual(subRes.certified, false);
assert.strictEqual(subRes.reason, 'INSUFFICIENT_BFT_QUORUM');
console.log('✓ Test 3: Sub-quorum Re-Genesis rejected fail-closed');

// Test 4: 2f+1 BFT certification (70% weight)
const validSigs = [
  { validatorId: 'v_0', sig: 's0' },
  { validatorId: 'v_1', sig: 's1' }
];
const certRes = engine.certifyReGenesis(proposal, validSigs);
assert.strictEqual(certRes.certified, true);
assert.strictEqual(engine.genesisEpoch, 1);
assert.strictEqual(engine.historicalBlocks.length, 0, 'Bloated block logs must be purged');
console.log('✓ Test 4: Re-Genesis executed: state preserved and history purged');

// Test 5: Verify account balance preservation
assert.strictEqual(engine.getAccountBalance('agent_alpha'), 5000);
assert.strictEqual(engine.getAccountBalance('agent_beta'), 3500);
console.log('✓ Test 5: Active balances preserved post-regenesis');

// Test 6: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_REGENESIS_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'bft_shard_regenesis_engine');
assert.strictEqual(report.genesisEpoch, 1);
assert.strictEqual(report.regenesisCount, 1);
console.log('✓ Test 6: Evidence report written to SAMPLE_SHARD_REGENESIS_REPORT.json');

console.log('All BFT Shard Re-Genesis Consensus Engine tests passed successfully!');
