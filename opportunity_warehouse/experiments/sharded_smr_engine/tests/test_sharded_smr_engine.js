const { ShardedSMREngine } = require('../lib/sharded_smr_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Sharded SMR Consensus Engine...');

const config = {
  shard_alpha: ['node_a0', 'node_a1', 'node_a2', 'node_a3'],
  shard_beta: ['node_b0', 'node_b1', 'node_b2', 'node_b3']
};

const engine = new ShardedSMREngine(config, 1);

// Test 1: Successful cross-shard atomic transaction
const tx1Ops = {
  shard_alpha: { reads: [], writes: { account_alpha: 95.00 } },
  shard_beta: { reads: [], writes: { account_beta: 5.00 } }
};

const res1 = engine.executeCrossShardTx('tx_cross_settlement_01', tx1Ops);
console.log('✓ Test 1: Cross-shard transaction successfully committed: ' + res1.status);
if (!res1.success || res1.participantShardCount !== 2) {
  throw new Error('Cross-shard transaction 1 failed');
}

// Verify values on both shards
const valA = engine.getShardValue('shard_alpha', 'account_alpha');
const valB = engine.getShardValue('shard_beta', 'account_beta');
console.log('✓ Test 2: State values verified: alpha=' + valA + ', beta=' + valB);
if (valA !== 95.00 || valB !== 5.00) {
  throw new Error('Shard states not updated accurately');
}

// Test 3: Lock conflict / partial failure triggers atomic Global Abort
// We simulate shard_alpha having an active competing lock by manually setting it
const shardAlpha = engine.shards.get('shard_alpha');
shardAlpha.nodes[0].locks.set('account_alpha', 'tx_competing_active');
shardAlpha.nodes[1].locks.set('account_alpha', 'tx_competing_active'); // Quorum blocked

const txConflictOps = {
  shard_alpha: { reads: [], writes: { account_alpha: 50.00 } },
  shard_beta: { reads: [], writes: { account_beta: 100.00 } }
};

const resConflict = engine.executeCrossShardTx('tx_conflict_fail', txConflictOps);
console.log('✓ Test 3: Conflicting transaction correctly aborted fail-closed: ' + resConflict.status);
if (resConflict.success || resConflict.status !== 'GLOBAL_ABORTED') {
  throw new Error('Lock conflict transaction should have been aborted');
}

// Verify beta state was NOT updated (all-or-nothing atomicity preserved)
const valBPostConflict = engine.getShardValue('shard_beta', 'account_beta');
if (valBPostConflict !== 5.00) {
  throw new Error('Atomicity violation: shard_beta modified during aborted transaction!');
}
console.log('✓ Test 4: All-or-nothing atomicity verified: uncommitted shard state rolled back');

// Test 5: Write verification report
const report = {
  experiment: 'sharded_smr_engine',
  phase: 479,
  timestamp: new Date().toISOString(),
  shardsConfigured: Object.keys(config),
  crossShardTx1: res1,
  conflictAbortTx: resConflict,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_SHARDED_SMR_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_SHARDED_SMR_REPORT.json');

console.log('All Sharded SMR Consensus tests passed successfully!');
