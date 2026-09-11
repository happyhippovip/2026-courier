const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BftShardCheckpointChainingEngine } = require('../lib/bft_shard_checkpoint_chaining_engine');

console.log('Testing BFT Shard Checkpoint Chaining Consensus Engine...');
const engine = new BftShardCheckpointChainingEngine();

// Test 1: Append Genesis Checkpoint
const cp0 = engine.appendCheckpoint(0, 'shard-0', '0xroot0', ['sig1', 'sig2']);
assert.strictEqual(cp0.index, 0);
assert.strictEqual(cp0.previousCheckpointHash, '0xgenesis');
console.log('✓ Test 1: Genesis checkpoint appended cleanly');

// Test 2: Append Chained Checkpoint
const cp1 = engine.appendCheckpoint(1, 'shard-0', '0xroot1', ['sig1', 'sig3']);
assert.strictEqual(cp1.index, 1);
assert.strictEqual(cp1.previousCheckpointHash, cp0.checkpointHash);
console.log('✓ Test 2: Epoch 1 checkpoint successfully linked to Genesis hash');

// Test 3: Verify Chain Integrity
const vRes = engine.verifyChainIntegrity();
assert.strictEqual(vRes.valid, true);
assert.strictEqual(vRes.chainLength, 2);
console.log('✓ Test 3: Merkle hash pointer chain integrity verified 100%');

const report = {
  test: 'BFT_SHARD_CHECKPOINT_CHAINING_ENGINE',
  passed: true,
  chainLength: engine.chain.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_BFT_CHECKPOINT_CHAINING_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 4: Evidence report written to SAMPLE_BFT_CHECKPOINT_CHAINING_REPORT.json');
console.log('All BFT Shard Checkpoint Chaining Consensus tests passed successfully!');
