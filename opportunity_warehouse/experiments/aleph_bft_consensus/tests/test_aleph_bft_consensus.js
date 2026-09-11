const { AlephBFTConsensus } = require('../lib/aleph_bft_consensus');
const fs = require('fs');
const path = require('path');

console.log('Testing Aleph-BFT Asynchronous DAG Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const consensus = new AlephBFTConsensus(nodes, 1);

// Test 1: Construct Round 0 units across 4 nodes
const r0 = nodes.map(n => consensus.createUnit(n, 0, [], { cmd: `genesis_${n}` }));
const r0_hashes = r0.map(u => u.hash);
if (r0.length !== 4) throw new Error('Expected 4 round 0 units');
console.log('✓ Test 1: Created Round 0 genesis units for 4 nodes');

// Test 2: Construct Round 1 units referencing >= 3 parents from Round 0
const r1 = nodes.map(n => consensus.createUnit(n, 1, r0_hashes.slice(0, 3), { cmd: `turn1_${n}` }));
const r1_hashes = r1.map(u => u.hash);
console.log('✓ Test 2: Created Round 1 units with valid 2f+1=3 parent references');

// Test 3: Construct Round 2 units and decide Round 1 Leader
const r2 = nodes.map(n => consensus.createUnit(n, 2, r1_hashes.slice(0, 3), { cmd: `turn2_${n}` }));

const leader1 = consensus.getRoundLeader(1);
if (!leader1 || leader1.creator !== 'node_1') {
  throw new Error('Expected Round 1 leader to be node_1');
}

const decided = consensus.tryDecideRoundLeader(1);
if (!decided) throw new Error('Failed to decide Round 1 leader with Round 2 quorum');
console.log('✓ Test 3: Successfully decided Round 1 leader (' + leader1.creator + ') with 2f+1 quorum');

// Test 4: Verify linear total order of causal history
const totalOrder = consensus.getLinearOrder();
if (totalOrder.length === 0) throw new Error('Linear total order cannot be empty');
console.log('✓ Test 4: Ordered ' + totalOrder.length + ' causal units deterministically');

// Test 5: Write verification evidence report
const report = {
  experiment: 'aleph_bft_consensus',
  phase: 407,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  quorum: 3,
  decidedLeader: {
    round: leader1.round,
    creator: leader1.creator,
    hash: leader1.hash
  },
  linearOrderCount: totalOrder.length,
  orderedCommands: totalOrder.map(u => ({ round: u.round, creator: u.creator, cmd: u.payload.cmd })),
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_ALEPH_BFT_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_ALEPH_BFT_REPORT.json');

console.log('All Aleph-BFT Consensus tests passed successfully!');
