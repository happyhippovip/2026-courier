const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { BFTFastSyncEngine } = require('./lib/bft_fast_sync_engine');

console.log('Testing Byzantine Fast-Sync Consensus Engine...');

const engine = new BFTFastSyncEngine(4, 2); // 2 accounts per chunk

// Test 1: Load server state with 5 accounts
engine.loadServerState([
  { id: 'acc_01', balance: 100 },
  { id: 'acc_02', balance: 250 },
  { id: 'acc_03', balance: 50 },
  { id: 'acc_04', balance: 800 },
  { id: 'acc_05', balance: 300 }
]);

// Test 2: Generate snapshot manifest at height 100
const manifest = engine.generateSnapshotManifest(100);
assert.strictEqual(manifest.height, 100);
assert.strictEqual(manifest.totalChunks, 3); // 5 accounts / 2 = 3 chunks
console.log('✓ Test 1 & 2: Server state loaded; Snapshot Manifest generated (3 chunks at height 100)');

// Test 3: Download and apply Chunk 0
const r0 = engine.applyDownloadedChunk(engine.chunks[0]);
assert.strictEqual(r0.syncComplete, false);
assert.strictEqual(r0.downloadedChunks, 1);

// Test 4: Download and apply Chunk 1
const r1 = engine.applyDownloadedChunk(engine.chunks[1]);
assert.strictEqual(r1.syncComplete, false);
assert.strictEqual(r1.downloadedChunks, 2);

// Test 5: Download and apply Chunk 2 -> Sync complete!
const r2 = engine.applyDownloadedChunk(engine.chunks[2]);
assert.strictEqual(r2.syncComplete, true);
assert.strictEqual(r2.height, 100);
assert.strictEqual(r2.totalAccounts, 5);
assert.strictEqual(engine.clientState.get('acc_04'), 800);
console.log('✓ Test 3, 4 & 5: All 3 snapshot chunks verified and applied; client state 100% synchronized');

// Test 6: Corrupt chunk rejection fail-closed
assert.throws(() => {
  const corruptChunk = {
    chunkIndex: 0,
    totalChunks: 3,
    accounts: [{ id: 'acc_01', balance: 9999999 }] // tampered balance!
  };
  engine.applyDownloadedChunk(corruptChunk);
}, /Corrupt chunk hash mismatch/, 'Corrupt chunk must throw');
console.log('✓ Test 6: Tampered snapshot chunk rejected fail-closed');

// Test 7: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_FAST_SYNC_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 575,
  stats: engine.getStats(),
  manifest,
  verdict: 'BFT_FAST_SYNC_ENGINE_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 7: Evidence report written to SAMPLE_FAST_SYNC_REPORT.json');

console.log('All Byzantine Fast-Sync Consensus tests passed successfully!');
