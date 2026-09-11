const { DumboBFTConsensus } = require('../lib/dumbo_bft_consensus');
const fs = require('fs');
const path = require('path');

console.log('Testing Dumbo-BFT Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const dumbo = new DumboBFTConsensus(nodes, 2, 1);

// Test 1: Submit proposals from 3 nodes (quorum 2f+1=3)
dumbo.submitProposal('node_0', [{ tx: 'solvency_audit_check' }]);
dumbo.submitProposal('node_1', [{ tx: 'settle_eur5_commercial_order' }]);
dumbo.submitProposal('node_2', [{ tx: 'prune_context_window_leaf' }]);

console.log('✓ Test 1: Submitted proposals from 3 nodes reaching quorum');

// Test 2: Select committee and finalize epoch 1
const finalize1 = dumbo.finalizeEpoch();
if (!finalize1 || finalize1.selectedCommittee.length !== 2) {
  throw new Error('Committee selection failed');
}
if (finalize1.totalCommittedTxs !== 2) {
  throw new Error('Expected 2 committed transactions, got ' + finalize1.totalCommittedTxs);
}
console.log('✓ Test 2: Finalized Epoch 1 with committee [' + finalize1.selectedCommittee.join(', ') + ']');

// Test 3: Epoch advances
if (dumbo.epoch !== 2) throw new Error('Epoch should be 2');
console.log('✓ Test 3: Epoch state advanced to 2');

// Test 4: Write verification report
const report = {
  experiment: 'dumbo_bft_consensus',
  phase: 443,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  committeeSize: 2,
  quorum: 3,
  finalizedEpochsCount: dumbo.committedEpochs.length,
  latestEpoch: finalize1,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_DUMBO_BFT_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_DUMBO_BFT_REPORT.json');

console.log('All Dumbo-BFT tests passed successfully!');
