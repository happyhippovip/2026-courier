const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTReanchoringEngine } = require('../lib/bft_reanchoring_engine');

console.log('Testing BFT Dynamic Epoch State Re-anchoring Consensus Engine...');

const engine = new BFTReanchoringEngine('node_0', 4, 1);

// Test 1: Anchor Proposal
const anchor = engine.proposeAnchor(10, '0xabcdef1234567890', '0xvalsethash123');
assert.strictEqual(anchor.epoch, 10);
assert.strictEqual(anchor.stateRoot, '0xabcdef1234567890');
console.log('✓ Test 1: Epoch 10 anchor proposal successfully constructed');

// Test 2: Quorum Certification
const sig0 = engine.signAnchor(anchor);
const sig1 = { epoch: 10, anchorHash: anchor.anchorHash, nodeId: 'node_1', signature: require('crypto').createHash('sha256').update('node_1:' + anchor.anchorHash + ':10').digest('hex') };
const sig2 = { epoch: 10, anchorHash: anchor.anchorHash, nodeId: 'node_2', signature: require('crypto').createHash('sha256').update('node_2:' + anchor.anchorHash + ':10').digest('hex') };

const certResult = engine.certifyAnchor(anchor, [sig0, sig1, sig2]);
assert.strictEqual(certResult.certified, true);
assert.strictEqual(certResult.certifiedAnchor.quorumCert.count, 3);
console.log('✓ Test 2: 2f+1 quorum certification validated with 3 node signatures');

// Test 3: Safe History Pruning
const pruneRes = engine.pruneHistory(10);
assert.strictEqual(pruneRes.prunedUpTo, 10);
console.log('✓ Test 3: Historical causal chain safely pruned behind certified anchor');

// Test 4: Fast Bootstrap Verification
const validBoot = engine.verifyBootstrappedNode(10, '0xabcdef1234567890');
assert.strictEqual(validBoot, true);
const invalidBoot = engine.verifyBootstrappedNode(10, '0xinvalidroot');
assert.strictEqual(invalidBoot, false);
console.log('✓ Test 4: Node bootstrap verification validated state root integrity');

// Test 5: Uncertified epoch pruning throws fail-closed
assert.throws(() => {
  engine.pruneHistory(99);
}, /has no certified anchor/);
console.log('✓ Test 5: Uncertified epoch pruning attempt rejected fail-closed');

// Test 6: Evidence Report Export
const evidenceReport = {
  experiment: 'bft_reanchoring_engine',
  timestamp: new Date().toISOString(),
  anchorEpoch: anchor.epoch,
  stateRoot: anchor.stateRoot,
  signaturesCollected: certResult.certifiedAnchor.quorumCert.count,
  prunedBeforeEpoch: engine.prunedBeforeEpoch,
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_REANCHORING_ENGINE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 6: Evidence report written to SAMPLE_REANCHORING_ENGINE_REPORT.json');

console.log('All BFT Re-anchoring Engine tests passed successfully!');
