const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTViewInterleavingEngine } = require('../lib/bft_view_interleaving_engine');

console.log('Testing BFT View-Interleaving Consensus Engine...');

const engine = new BFTViewInterleavingEngine('node_leader', 4, 1);

// Test 1: Concurrent proposals across Lane Alpha and Lane Beta
const blkAlpha = engine.proposeInLane('lane_alpha', 10, { op: 'PAYMENT', amount: 50 });
const blkBeta = engine.proposeInLane('lane_beta', 11, { op: 'STAKE_LOCK', amount: 200 });

assert.strictEqual(blkAlpha.laneId, 'lane_alpha');
assert.strictEqual(blkBeta.laneId, 'lane_beta');
console.log('✓ Test 1: Concurrent interleaved proposals in 2 lanes constructed');

// Test 2: Barrier synchronization with 2f+1 quorum certification
const payloadHash = require('crypto').createHash('sha256').update(JSON.stringify({
  barrierEpoch: 1,
  laneBlockHashes: [blkAlpha.hash, blkBeta.hash]
})).digest('hex');

const sigs = [
  { nodeId: 'node_0', signature: require('crypto').createHash('sha256').update('node_0:' + payloadHash).digest('hex') },
  { nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + payloadHash).digest('hex') },
  { nodeId: 'node_2', signature: require('crypto').createHash('sha256').update('node_2:' + payloadHash).digest('hex') }
];

const res = engine.certifyInterleavedEpoch(1, [blkAlpha.hash, blkBeta.hash], sigs);
assert.strictEqual(res.committed, true);
assert.strictEqual(res.totalCommitted, 2);
console.log('✓ Test 2: Interleaved epoch successfully committed across multi-lane barrier (blocks: 2)');

// Test 3: Total order verification
assert.deepStrictEqual(res.blocks.map(b => b.laneId), ['lane_alpha', 'lane_beta']);
console.log('✓ Test 3: Deterministic total ordering preserved across interleaved lanes');

// Test 4: Insufficient signatures rejected fail-closed
const rejected = engine.certifyInterleavedEpoch(2, [blkAlpha.hash], [sigs[0]]);
assert.strictEqual(rejected.committed, false);
console.log('✓ Test 4: Sub-quorum certification attempt rejected fail-closed');

// Test 5: Export Evidence Report
const evidenceReport = {
  experiment: 'bft_view_interleaving_engine',
  timestamp: new Date().toISOString(),
  committedEpochs: engine.interleavedCommitted.length,
  totalInterleavedBlocks: res.totalCommitted,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_VIEW_INTERLEAVING_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 5: Evidence report written to SAMPLE_VIEW_INTERLEAVING_REPORT.json');

console.log('All BFT View-Interleaving Consensus Engine tests passed successfully!');
