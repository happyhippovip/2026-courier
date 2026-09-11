const { PipelinedHotStuffEngine } = require('../lib/pipelined_hotstuff_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Pipelined HotStuff Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const phs = new PipelinedHotStuffEngine(nodes, 1);

// Block 1 (View 1)
const b1 = phs.propose('node_0', { tx: 'tx_b1_settlement', amount: 5.00 });
const qc1 = phs.voteAndCreateQC(b1.hash);
console.log('✓ Test 1: Block 1 proposed and certified in View 1 (qcId: ' + qc1.qcId.slice(0, 8) + '...)');

// Block 2 (View 2) extends Block 1
const b2 = phs.propose('node_1', { tx: 'tx_b2_state_sync' });
const qc2 = phs.voteAndCreateQC(b2.hash);
console.log('✓ Test 2: Block 2 proposed and certified in View 2 (1-chain formed)');

if (phs.getCommittedBlocks().length !== 0) {
  throw new Error('Premature commit before 3-chain completion');
}

// Block 3 (View 3) extends Block 2 (Triggers 3-chain commit for Block 1!)
const b3 = phs.propose('node_2', { tx: 'tx_b3_checkpoint' });
const qc3 = phs.voteAndCreateQC(b3.hash);

const committed = phs.getCommittedBlocks();
console.log('✓ Test 3: Block 3 proposed in View 3; committed blocks count: ' + committed.length);
if (committed.length !== 1 || committed[0].hash !== b1.hash) {
  throw new Error('Pipelined 3-chain commit rule failed for Block 1');
}
console.log('✓ Test 4: Block 1 (' + committed[0].payload.tx + ') committed via pipelined 3-chain rule!');

// Block 4 (View 4) extends Block 3 (Commits Block 2!)
const b4 = phs.propose('node_3', { tx: 'tx_b4_next' });
phs.voteAndCreateQC(b4.hash);

if (phs.getCommittedBlocks().length !== 2) {
  throw new Error('Expected 2 committed blocks after Block 4');
}
console.log('✓ Test 5: Block 2 successfully committed via subsequent pipelined proposal');

// Write verification report
const report = {
  experiment: 'pipelined_hotstuff_engine',
  phase: 495,
  timestamp: new Date().toISOString(),
  nodes: 4,
  quorum: 3,
  pipelineDepth: 3,
  totalCommitted: phs.getCommittedBlocks().length,
  committedPayloads: phs.getCommittedBlocks().map(b => b.payload.tx),
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_PIPELINED_HOTSTUFF_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 6: Evidence report written to SAMPLE_PIPELINED_HOTSTUFF_REPORT.json');

console.log('All Pipelined HotStuff Consensus tests passed successfully!');
