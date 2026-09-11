const { NarwhalHotStuff2Engine } = require('../lib/narwhal_hotstuff2_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Narwhal-HotStuff-2 Hybrid Consensus Engine...');
const validators = ['val_0', 'val_1', 'val_2', 'val_3'];
const hybrid = new NarwhalHotStuff2Engine(validators, 1);

// Test 1: Narwhal Round 1 DAG Certificates
const c1 = hybrid.createBatchAndCertificate('val_0', 1, [], ['tx_val0_a', 'tx_val0_b']);
const c2 = hybrid.createBatchAndCertificate('val_1', 1, [], ['tx_val1_a']);
console.log('✓ Test 1: Generated Narwhal Round 1 Availability Certificates (' + c1.id.slice(0, 8) + '..., ' + c2.id.slice(0, 8) + '...)');

// Test 2: Narwhal Round 2 DAG Certificate referencing Round 1
const c3 = hybrid.createBatchAndCertificate('val_2', 2, [c1.id, c2.id], ['tx_val2_round2']);
console.log('✓ Test 2: Generated Narwhal Round 2 Certificate referencing causal history');

// Test 3: HotStuff-2 sequences Round 2 certificate in Block 1
const b1 = hybrid.propose('val_0', [c3]);
const qc1 = hybrid.voteAndCreateQC(b1.hash);
console.log('✓ Test 3: Proposed Block 1 with Narwhal Certificate; QC formed in View 1');

// Test 4: Propose Block 2 to commit Block 1 via 2-chain rule
const c4 = hybrid.createBatchAndCertificate('val_3', 3, [c3.id], ['tx_val3_commercial_settle']);
const b2 = hybrid.propose('val_1', [c4]);
const qc2 = hybrid.voteAndCreateQC(b2.hash);

if (hybrid.committedBlocks.length !== 1 || hybrid.committedBlocks[0].hash !== b1.hash) {
  throw new Error('2-chain commit failed to commit Block 1');
}
console.log('✓ Test 4: Block 1 committed via HotStuff-2 2-chain rule');

// Test 5: Verify deterministic topological order of transactions
const txs = hybrid.getOrderedTransactions();
console.log('✓ Test 5: Causal ordering finalized transactions: ' + JSON.stringify(txs));

// Invariant: C1 and C2 txs must appear before C3 txs
const idxVal0 = txs.indexOf('tx_val0_a');
const idxVal1 = txs.indexOf('tx_val1_a');
const idxVal2 = txs.indexOf('tx_val2_round2');
if (idxVal0 === -1 || idxVal1 === -1 || idxVal2 === -1 || idxVal0 > idxVal2 || idxVal1 > idxVal2) {
  throw new Error('Causal ordering violation in Narwhal DAG past');
}

// Write evidence report
const report = {
  experiment: 'narwhal_hotstuff2_engine',
  phase: 463,
  timestamp: new Date().toISOString(),
  validators: 4,
  quorum: 3,
  dagCertificatesCreated: 4,
  committedBlocks: hybrid.committedBlocks.length,
  orderedTransactionCount: txs.length,
  linearizedTransactions: txs,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_NARWHAL_HOTSTUFF2_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 6: Evidence report written to SAMPLE_NARWHAL_HOTSTUFF2_REPORT.json');

console.log('All Narwhal-HotStuff-2 Consensus tests passed successfully!');
