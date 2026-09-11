const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTShardGCEngine } = require('../lib/bft_shard_gc_engine');

console.log('Testing BFT Dynamic Shard State Garbage Collection Consensus Engine...');

const engine = new BFTShardGCEngine('shard_alpha', 3);

// Test 1: Insert keys with epoch expiration
engine.setKey('active_token_1', { balance: 100 }, 20); // expires at epoch 20
engine.setKey('expired_lock_1', { balance: 0 }, 5);    // expired at epoch 5
engine.setKey('expired_lock_2', { balance: 0 }, 8);    // expired at epoch 8

assert.strictEqual(engine.getKey('active_token_1').balance, 100);
assert.strictEqual(engine.getKey('expired_lock_1').balance, 0);
console.log('✓ Test 1: Initial state keys populated with epoch expiration tags');

// Test 2: Identify GC candidates at Epoch 10
const proposal = engine.proposeGCCandidates(10);
assert.deepStrictEqual(proposal.deadKeys.sort(), ['expired_lock_1', 'expired_lock_2']);
console.log('✓ Test 2: Dead keys accurately flagged for GC at epoch 10:', proposal.deadKeys);

// Test 3: Quorum certification and pruning
const sig0 = { nodeId: 'node_0', signature: require('crypto').createHash('sha256').update('node_0:' + proposal.hash + ':10').digest('hex') };
const sig1 = { nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + proposal.hash + ':10').digest('hex') };
const sig2 = { nodeId: 'node_2', signature: require('crypto').createHash('sha256').update('node_2:' + proposal.hash + ':10').digest('hex') };

const gcRes = engine.certifyAndPrune(proposal, [sig0, sig1, sig2]);
assert.strictEqual(gcRes.pruned, true);
assert.strictEqual(gcRes.prunedCount, 2);
assert.strictEqual(engine.getKey('expired_lock_1'), null);
assert.strictEqual(engine.getKey('active_token_1').balance, 100);
console.log('✓ Test 3: 2f+1 quorum certified GC execution: dead keys pruned, live keys preserved');

// Test 4: Sub-quorum rejected fail-closed
const prop2 = engine.proposeGCCandidates(15);
const resFail = engine.certifyAndPrune(prop2, [sig0]);
assert.strictEqual(resFail.pruned, false);
console.log('✓ Test 4: Sub-quorum GC attempt rejected fail-closed');

// Test 5: Export evidence report
const evidenceReport = {
  experiment: 'bft_shard_gc_engine',
  timestamp: new Date().toISOString(),
  shardId: engine.shardId,
  totalPrunedRecords: engine.prunedHistory.length,
  lastPruneCount: gcRes.prunedCount,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_GC_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 5: Evidence report written to SAMPLE_SHARD_GC_REPORT.json');

console.log('All BFT Shard Garbage Collection Engine tests passed successfully!');
