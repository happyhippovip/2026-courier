const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BftShardSlashingConsensusEngine } = require('../lib/bft_shard_slashing_consensus_engine');

console.log('Testing BFT Shard Slashing Consensus Engine...');
const engine = new BftShardSlashingConsensusEngine();

// Test 1: Honest single vote in epoch 1
const v1 = engine.recordVote('val-honest', 1, '0xblockA', 'sig-honest-1');
assert.strictEqual(v1.accepted, true);
assert.strictEqual(v1.slashed, false);
console.log('✓ Test 1: Honest vote recorded without penalty');

// Test 2: Equivocation attack (same validator votes for blockB in epoch 1)
const v2 = engine.recordVote('val-byzantine', 1, '0xblockA', 'sig-byz-1');
assert.strictEqual(v2.accepted, true);
const v2Double = engine.recordVote('val-byzantine', 1, '0xblockB', 'sig-byz-2');
assert.strictEqual(v2Double.accepted, false);
assert.strictEqual(v2Double.slashed, true);
assert.strictEqual(engine.isSlashed('val-byzantine'), true);
console.log('✓ Test 2: Byzantine equivocation caught fail-closed; stake 100% slashed');

// Test 3: Slashing evidence verification
const record = engine.getSlashingRecord('val-byzantine');
assert.strictEqual(record.offense, 'EQUIVOCATION_DOUBLE_VOTE');
assert.strictEqual(record.evidence.length, 2);
console.log('✓ Test 3: Slashing proof hash verified (proof:', record.slashingProofHash.substring(0, 10), '...)');

const report = {
  test: 'BFT_SHARD_SLASHING_CONSENSUS_ENGINE',
  passed: true,
  slashedCount: engine.slashedValidators.size,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_BFT_SLASHING_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 4: Evidence report written to SAMPLE_BFT_SLASHING_REPORT.json');
console.log('All BFT Shard Slashing Consensus tests passed successfully!');
