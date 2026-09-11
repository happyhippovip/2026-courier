const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTShardViewSyncEngine } = require('../lib/bft_shard_viewsync_engine');

console.log('Testing BFT Shard View-Synchronization Consensus Engine...');
const engine = new BFTShardViewSyncEngine('shard-alpha-01', 4, 1500);

// Validator 0 triggers view change timeout
const res1 = engine.triggerTimeout('val-0');
assert.strictEqual(res1.status, 'AWAITING_QUORUM');
assert.strictEqual(res1.currentVotes, 1);

// Validator 1 triggers view change timeout
const res2 = engine.triggerTimeout('val-1');
assert.strictEqual(res2.status, 'AWAITING_QUORUM');
assert.strictEqual(res2.currentVotes, 2);

// Validator 2 triggers view change timeout -> Quorum (2f+1 = 3) reached
const res3 = engine.triggerTimeout('val-2');
assert.strictEqual(res3.status, 'VIEW_SYNCHRONIZED');
assert.strictEqual(res3.newView, 1);
assert.strictEqual(res3.certificate.voterCount, 3);
assert.ok(res3.certificate.quorumCertificateHash.length === 64);

const status = engine.getSynchronizationStatus();
assert.strictEqual(status.currentView, 1);
assert.strictEqual(status.totalViewsSynchronized, 1);

const report = {
  experiment: 'bft_shard_viewsync_engine',
  status: 'VERIFIED',
  testSuite: 'test_bft_shard_viewsync_engine',
  viewSyncStatus: status,
  lastCertificate: res3.certificate,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(
  path.join(__dirname, 'SAMPLE_BFT_VIEWSYNC_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);

console.log('✓ BFT Shard View-Synchronization Consensus Engine verified successfully.');
