const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { PBFTNode, PBFTCoordinator } = require('./lib/pbft_consensus_coordinator');

console.log('Testing PBFT Byzantine Consensus Coordinator...');

// N = 4 nodes, can tolerate f = 1 Byzantine node (4 = 3*1 + 1)
const n1 = new PBFTNode('node-0', 4, false); // Leader
const n2 = new PBFTNode('node-1', 4, false);
const n3 = new PBFTNode('node-2', 4, false);
const n4 = new PBFTNode('node-3', 4, true);  // Byzantine fault injector

const coordinator = new PBFTCoordinator([n1, n2, n3, n4]);
const result = coordinator.runConsensus('tx-pbft-900', { invariant: 'zero-spend-maintained' });

// Test 1: Honest quorum reached despite 1 Byzantine node
assert.strictEqual(result.allHonestCommitted, true);
assert.strictEqual(result.status, 'COMMITTED');
assert.strictEqual(n1.state, 'COMMITTED');
assert.strictEqual(n2.state, 'COMMITTED');
assert.strictEqual(n3.state, 'COMMITTED');
assert.strictEqual(n4.state, 'IDLE'); // Byzantine node refused to commit
console.log('✓ Test 1: Consensus successfully reached across 3 honest nodes with 1 Byzantine node safely quarantined');

// Test 2: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 319,
  component: 'pbft_consensus_coordinator',
  clusterSize: 4,
  toleratedFailuresF: 1,
  byzantineNodes: ['node-3'],
  consensusResult: result,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_PBFT_CONSENSUS_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 2: Evidence report written to SAMPLE_PBFT_CONSENSUS_REPORT.json');
console.log('All PBFT Consensus Coordinator tests passed successfully!');
