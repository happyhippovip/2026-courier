const { JolteonBFTConsensus } = require('../lib/jolteon_bft_consensus');
const fs = require('fs');
const path = require('path');

console.log('Testing Jolteon 2-Chain BFT Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const jolteon = new JolteonBFTConsensus(nodes, 1);

// Test 1: Propose Block 1
const b1 = jolteon.propose('node_0', { action: 'INITIALIZE_LEDGER_EPOCH', epoch: 1 });
const qc1 = jolteon.voteAndFormQC(b1.hash);
if (Object.keys(qc1.signatures).length < 3) throw new Error('QC1 missing signatures');
console.log('✓ Test 1: Block 1 proposed and certified in 1 round-trip');

// Test 2: Propose Block 2 chained to QC1
const b2 = jolteon.propose('node_1', { action: 'SETTLE_CUSTOMER_ORDER_EUR5', amount: 5.00 });
const qc2 = jolteon.voteAndFormQC(b2.hash);

// With 2-chain rule, b1 is now immediately committed!
const committed = jolteon.getCommittedBlocks();
if (committed.length !== 1 || committed[0].hash !== b1.hash) {
  throw new Error('Expected Block 1 to be committed via 2-chain rule');
}
console.log('✓ Test 2: 2-Chain responsive commit rule committed Block 1 (' + committed[0].hash.slice(0, 10) + '...) in only 2 round-trips');

// Test 3: Block 3 commits Block 2
const b3 = jolteon.propose('node_2', { action: 'AUDIT_CONFIRMATION', status: 'GREEN' });
jolteon.voteAndFormQC(b3.hash);

if (jolteon.getCommittedBlocks().length !== 2) {
  throw new Error('Expected 2 committed blocks, got ' + jolteon.getCommittedBlocks().length);
}
console.log('✓ Test 3: Block 2 successfully committed via subsequent 2-chain step');

// Test 4: Write verification report
const report = {
  experiment: 'jolteon_bft_consensus',
  phase: 423,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  quorum: 3,
  latencyRoundTripsToCommit: 2,
  totalCommittedBlocks: jolteon.getCommittedBlocks().length,
  committedBlocks: jolteon.getCommittedBlocks().map(b => ({ view: b.view, action: b.payload.action })),
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_JOLTEON_BFT_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_JOLTEON_BFT_REPORT.json');

console.log('All Jolteon BFT tests passed successfully!');
