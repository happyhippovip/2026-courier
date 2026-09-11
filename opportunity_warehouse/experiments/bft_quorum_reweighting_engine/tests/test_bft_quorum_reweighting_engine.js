const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTQuorumReweightingEngine } = require('../lib/bft_quorum_reweighting_engine');

console.log('Testing BFT Dynamic Quorum Re-weighting Consensus Engine...');

const initialWeights = {
  node_0: 40,
  node_1: 30,
  node_2: 30
};
const engine = new BFTQuorumReweightingEngine('node_0', initialWeights);

// Test 1: Quorum calculation
assert.strictEqual(engine.getTotalWeight(), 100);
assert.strictEqual(engine.getQuorumThreshold(), 67); // floor(200/3) + 1 = 67
console.log('✓ Test 1: Quorum threshold accurately calculated as 67 for total weight 100');

// Test 2: Proposal and Quorum Certification
const newWeights = {
  node_0: 50,
  node_1: 25,
  node_2: 25
};
const prop = engine.proposeReweighting(1, newWeights, { note: 'REWEIGHT_DUE_TO_PERFORMANCE' });

// node_0 (40) and node_1 (30) sign -> weight 70 >= 67
const sig0 = { nodeId: 'node_0', signature: require('crypto').createHash('sha256').update('node_0:' + prop.hash + ':1').digest('hex') };
const sig1 = { nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + prop.hash + ':1').digest('hex') };

const res = engine.certifyReweighting(prop, [sig0, sig1]);
assert.strictEqual(res.committed, true);
assert.strictEqual(res.commitRecord.accumulatedWeight, 70);
assert.strictEqual(engine.currentEpoch, 1);
assert.strictEqual(engine.weights.get('node_0'), 50);
console.log('✓ Test 2: Re-weighting successfully certified with 70/67 supermajority weight');

// Test 3: Sub-quorum rejection
const prop2 = engine.proposeReweighting(2, { node_0: 60, node_1: 20, node_2: 20 }, { note: 'NEXT_EPOCH' });
// node_1 (25) alone -> weight 25 < 67 required
const sigSingle = { nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + prop2.hash + ':2').digest('hex') };
const resFail = engine.certifyReweighting(prop2, [sigSingle]);
assert.strictEqual(resFail.committed, false);
assert.strictEqual(resFail.reason, 'INSUFFICIENT_WEIGHT_QUORUM');
console.log('✓ Test 3: Sub-quorum proposal rejected fail-closed');

// Test 4: Evidence report export
const evidenceReport = {
  experiment: 'bft_quorum_reweighting_engine',
  timestamp: new Date().toISOString(),
  finalEpoch: engine.currentEpoch,
  currentWeights: Object.fromEntries(engine.weights),
  totalWeight: engine.getTotalWeight(),
  quorumThreshold: engine.getQuorumThreshold(),
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_QUORUM_REWEIGHTING_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_QUORUM_REWEIGHTING_REPORT.json');

console.log('All BFT Quorum Re-weighting Engine tests passed successfully!');
