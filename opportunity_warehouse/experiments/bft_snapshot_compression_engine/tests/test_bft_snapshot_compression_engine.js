const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTSnapshotCompressionEngine } = require('../lib/bft_snapshot_compression_engine');

console.log('Testing BFT Dynamic State Snapshot Compression Consensus Engine...');

const engine = new BFTSnapshotCompressionEngine('node_0', 4, 1);

// Test 1: Compression of state epoch
const stateEpoch0 = { 'account_A': 100, 'account_B': 200, 'account_C': 300 };
const stateEpoch1 = { 'account_A': 150, 'account_B': 200, 'account_C': 350, 'account_D': 50 };

const snap = engine.compressState(1, stateEpoch1, stateEpoch0);
assert.strictEqual(snap.epoch, 1);
assert(snap.compressedSize > 0);
console.log('✓ Test 1: State delta compression verified for Epoch 1');

// Test 2: Multi-node threshold signatures
const sig0 = engine.signSnapshot(1);
const sig1 = { epoch: 1, stateHash: snap.stateHash, deltaHash: snap.deltaHash, nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + snap.stateHash + ':1').digest('hex') };
const sig2 = { epoch: 1, stateHash: snap.stateHash, deltaHash: snap.deltaHash, nodeId: 'node_2', signature: require('crypto').createHash('sha256').update('node_2:' + snap.stateHash + ':1').digest('hex') };

const certResult = engine.certifySnapshot(1, [sig0, sig1, sig2]);
assert.strictEqual(certResult.certified, true);
assert.strictEqual(certResult.certification.signatureCount, 3);
console.log('✓ Test 2: Byzantine 2f+1 quorum certification succeeded with 3 valid signatures');

// Test 3: State restoration & integrity verification
const restored = engine.restoreState(1, stateEpoch0);
assert.deepStrictEqual(restored, stateEpoch1, 'Restored state must match original epoch state');
console.log('✓ Test 3: Fast state restoration from compressed snapshot matches ground truth');

// Test 4: Corrupted snapshot rejection
assert.throws(() => {
  const corruptedEngine = new BFTSnapshotCompressionEngine('node_corrupt', 4, 1);
  corruptedEngine.snapshots.set(1, { ...snap, payload: Buffer.from(JSON.stringify({ 'account_A': 999 })).toString('base64') });
  corruptedEngine.certifiedSnapshots.set(1, {
    epoch: 1,
    snapshot: { ...snap, payload: Buffer.from(JSON.stringify({ 'account_A': 999 })).toString('base64') },
    signatureCount: 3
  });
  corruptedEngine.restoreState(1, stateEpoch0);
}, /Integrity verification failed/);
console.log('✓ Test 4: Corrupted snapshot payload rejected fail-closed');

// Test 5: Export evidence report
const evidenceReport = {
  experiment: 'bft_snapshot_compression_engine',
  timestamp: new Date().toISOString(),
  epoch: 1,
  compressionStats: {
    originalSize: snap.originalSize,
    compressedSize: snap.compressedSize,
    compressionRatio: snap.compressionRatio
  },
  quorumPassed: certResult.certified,
  signaturesCollected: certResult.certification.signatureCount,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SNAPSHOT_COMPRESSION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 5: Evidence report written to SAMPLE_SNAPSHOT_COMPRESSION_REPORT.json');

console.log('All BFT Snapshot Compression Engine tests passed successfully!');
