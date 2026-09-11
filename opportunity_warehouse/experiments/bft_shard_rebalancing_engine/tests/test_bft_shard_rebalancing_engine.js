const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTShardRebalancingEngine } = require('../lib/bft_shard_rebalancing_engine');

console.log('Testing BFT Dynamic Shard State Re-balancing Consensus Engine...');

const engine = new BFTShardRebalancingEngine('shard_0', 2);
engine.setRoutingTable({
  'a': 'shard_0',
  'b': 'shard_0',
  'c': 'shard_1',
  'd': 'shard_1'
});

// Test 1: Load Imbalance Detection
engine.recordLoad('shard_0', 500);
engine.recordLoad('shard_1', 100);
const imbalance = engine.detectImbalance(2.0);
assert.strictEqual(imbalance.imbalanced, true);
assert.strictEqual(imbalance.hotspot, 'shard_0');
assert.strictEqual(imbalance.ratio, 5.0);
console.log('✓ Test 1: Shard hotspot imbalance accurately detected (ratio: 5.0)');

// Test 2: Propose and Certify Rebalance Migration
const proposal = engine.proposeRebalance(1, {
  sourceShard: 'shard_0',
  targetShard: 'shard_1',
  prefixes: ['b']
});

const sig0 = { nodeId: 'node_0', signature: require('crypto').createHash('sha256').update('node_0:' + proposal.hash + ':1').digest('hex') };
const sig1 = { nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + proposal.hash + ':1').digest('hex') };
const sig2 = { nodeId: 'node_2', signature: require('crypto').createHash('sha256').update('node_2:' + proposal.hash + ':1').digest('hex') };

const res = engine.certifyRebalance(proposal, [sig0, sig1, sig2], 3);
assert.strictEqual(res.committed, true);
assert.strictEqual(res.commitRecord.signers.length, 3);
console.log('✓ Test 2: Atomic cross-shard state re-balancing committed with 2f+1 quorum');

// Test 3: Routing table verified after migration
assert.strictEqual(engine.routeKey('apple'), 'shard_0'); // prefix 'a' remains shard_0
assert.strictEqual(engine.routeKey('banana'), 'shard_1'); // prefix 'b' migrated to shard_1
console.log('✓ Test 3: Dynamic routing table updated: prefix b routes to shard_1');

// Test 4: Sub-quorum rejected fail-closed
const prop2 = engine.proposeRebalance(2, { sourceShard: 'shard_1', targetShard: 'shard_0', prefixes: ['c'] });
const resFail = engine.certifyRebalance(prop2, [sig0], 3);
assert.strictEqual(resFail.committed, false);
console.log('✓ Test 4: Sub-quorum re-balancing rejected fail-closed');

// Test 5: Export evidence report
const evidenceReport = {
  experiment: 'bft_shard_rebalancing_engine',
  timestamp: new Date().toISOString(),
  imbalanceDetected: imbalance,
  lastRebalance: res.commitRecord,
  finalRoutingTable: Object.fromEntries(engine.routingTable),
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_REBALANCING_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 5: Evidence report written to SAMPLE_SHARD_REBALANCING_REPORT.json');

console.log('All BFT Shard Re-balancing Engine tests passed successfully!');
