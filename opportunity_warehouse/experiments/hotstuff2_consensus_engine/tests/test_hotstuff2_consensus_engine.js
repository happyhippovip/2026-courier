const { HotStuff2ConsensusEngine } = require('../lib/hotstuff2_consensus_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing HotStuff-2 Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const hs2 = new HotStuff2ConsensusEngine(nodes, 1);

// Test 1: Propose Block 1
const b1 = hs2.propose('node_0', { tx: 'accumulator_root_sync', root: '0x123abc' });
const qc1 = hs2.voteAndCreateQC(b1.hash);
if (!qc1 || Object.keys(qc1.signatures).length < 3) throw new Error('QC1 creation failed');
console.log('✓ Test 1: Block 1 proposed and certified with quorum 2f+1=3 in View 1');

// Test 2: Propose Block 2 referencing QC1 (Triggers 2-chain commit of Block 1)
const b2 = hs2.propose('node_1', { tx: 'settle_commercial_revenue_eur5', amount: 5.00 });
const qc2 = hs2.voteAndCreateQC(b2.hash);

const committed = hs2.getCommittedBlocks();
if (committed.length !== 1 || committed[0].hash !== b1.hash) {
  throw new Error('HotStuff-2 two-chain commit failed for Block 1');
}
console.log('✓ Test 2: HotStuff-2 two-chain rule committed Block 1 (' + committed[0].hash.slice(0, 10) + '...) in only 2 rounds');

// Test 3: Block 3 commits Block 2
const b3 = hs2.propose('node_2', { tx: 'state_checkpoint_pass', status: 'GREEN' });
hs2.voteAndCreateQC(b3.hash);

if (hs2.getCommittedBlocks().length !== 2) {
  throw new Error('Expected 2 committed blocks, got ' + hs2.getCommittedBlocks().length);
}
console.log('✓ Test 3: Block 2 committed via subsequent chained proposal in View 3');

// Test 4: Write verification report
const report = {
  experiment: 'hotstuff2_consensus_engine',
  phase: 459,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  quorum: 3,
  commitLatencyRoundTrips: 2,
  totalCommitted: hs2.getCommittedBlocks().length,
  committedBlocks: hs2.getCommittedBlocks().map(b => ({ view: b.view, tx: b.payload.tx })),
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_HOTSTUFF2_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_HOTSTUFF2_REPORT.json');

console.log('All HotStuff-2 Consensus tests passed successfully!');
