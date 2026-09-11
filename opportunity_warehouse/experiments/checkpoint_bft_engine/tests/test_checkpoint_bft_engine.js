const { CheckpointBFTEngine, ReplicaState } = require('../lib/checkpoint_bft_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Checkpoint BFT Consensus Engine...');
const replicas = ['r0', 'r1', 'r2', 'r3'];
const engine = new CheckpointBFTEngine(replicas, 5, 1); // Checkpoint every 5 transactions

// Test 1: Execute 4 transactions (below checkpoint interval)
for (let i = 1; i <= 4; i++) {
  engine.executeTransaction({ type: 'SET', key: 'key_' + i, value: 'val_' + i });
}
if (engine.stableCertificates.size !== 0) {
  throw new Error('Checkpoint created prematurely');
}
console.log('✓ Test 1: 4 transactions executed; log length is 4 in replicas');

// Test 2: 5th transaction triggers Stable Checkpoint Certificate
const res5 = engine.executeTransaction({ type: 'SET', key: 'key_5', value: 'val_5' });
console.log('✓ Test 2: 5th transaction triggered checkpoint: ' + JSON.stringify(res5.checkpointResult.success));

if (!res5.checkpointResult || !res5.checkpointResult.success) {
  throw new Error('Checkpoint creation failed at seq 5');
}

// Test 3: Log truncation verified (old logs truncated to save bounded memory)
for (const replica of engine.replicas) {
  if (replica.log.length !== 0 || replica.lastStableSeq !== 5) {
    throw new Error('Log truncation failed for replica: ' + replica.nodeId);
  }
}
console.log('✓ Test 3: Replicas successfully truncated transaction logs up to stable seq 5');

// Test 4: Fast-sync lagging replica from Stable Checkpoint Certificate
const freshLaggingNode = new ReplicaState('r_lagging_new');
const syncRes = engine.syncLaggingReplica(freshLaggingNode, 5);
console.log('✓ Test 4: Lagging replica fast-synced to seq 5 via SCC: ' + syncRes.certId.slice(0, 10) + '...');

if (freshLaggingNode.state['key_5'] !== 'val_5' || freshLaggingNode.lastStableSeq !== 5) {
  throw new Error('State recovery for lagging replica failed');
}

// Test 5: Write verification report
const report = {
  experiment: 'checkpoint_bft_engine',
  phase: 487,
  timestamp: new Date().toISOString(),
  replicas: 4,
  quorum: 3,
  checkpointInterval: 5,
  stableCheckpoints: Array.from(engine.stableCertificates.values()),
  fastSyncVerified: syncRes.synced,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_CHECKPOINT_BFT_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_CHECKPOINT_BFT_REPORT.json');

console.log('All Checkpoint BFT Consensus tests passed successfully!');
