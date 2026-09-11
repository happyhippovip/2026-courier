const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTShardCrossLinkEngine } = require('../lib/bft_shard_crosslink_engine');

console.log('Testing BFT Shard Cross-Link Finality Consensus Engine...');

const engine = new BFTShardCrossLinkEngine('hub_node', 3);

// Test 1: Propose and finalize Cross-Link
const payload = require('crypto').createHash('sha256').update(JSON.stringify({
  shardId: 'shard_0',
  shardBlockNumber: 42,
  stateRoot: '0xstateroot42'
})).digest('hex');

const sigs = [
  { nodeId: 'node_0', signature: require('crypto').createHash('sha256').update('node_0:' + payload).digest('hex') },
  { nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + payload).digest('hex') },
  { nodeId: 'node_2', signature: require('crypto').createHash('sha256').update('node_2:' + payload).digest('hex') }
];

const res = engine.proposeCrossLink('shard_0', 42, '0xstateroot42', sigs);
assert.strictEqual(res.finalized, true);
assert.strictEqual(res.crossLinkRecord.signers.length, 3);
console.log('✓ Test 1: Shard 0 block 42 cross-link finalized into hub beacon chain');

// Test 2: Verify Finality Query
assert.strictEqual(engine.verifyFinality(res.crossLinkRecord.crossLinkId), true);
assert.strictEqual(engine.verifyFinality('0xnonexistent'), false);
console.log('✓ Test 2: Irreversible cross-link finality query verified');

// Test 3: Sub-quorum rejected fail-closed
const resFail = engine.proposeCrossLink('shard_1', 10, '0xstateroot10', [sigs[0]]);
assert.strictEqual(resFail.finalized, false);
console.log('✓ Test 3: Sub-quorum cross-link attempt rejected fail-closed');

// Test 4: Export evidence report
const evidenceReport = {
  experiment: 'bft_shard_crosslink_engine',
  timestamp: new Date().toISOString(),
  totalCrossLinksFinalized: engine.crossLinks.size,
  lastRecord: res.crossLinkRecord,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_CROSSLINK_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_SHARD_CROSSLINK_REPORT.json');

console.log('All BFT Shard Cross-Link Engine tests passed successfully!');
