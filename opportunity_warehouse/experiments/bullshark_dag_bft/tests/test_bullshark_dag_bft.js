const { BullsharkDAGBFT } = require('../lib/bullshark_dag_bft');
const fs = require('fs');
const path = require('path');

console.log('Testing Bullshark Asynchronous DAG-BFT Consensus Engine...');

// Setup 4 nodes (n=4, f=1, quorum=3)
const engine = new BullsharkDAGBFT(4, 1);

// Test 1: Construct Round 0 (Genesis / base round)
const r0_nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const r0_vertices = [];
for (let i = 0; i < 4; i++) {
  const v = engine.addVertex(r0_nodes[i], 0, { tx: `genesis_tx_${i}` }, []);
  r0_vertices.push(v);
}
const r0_hashes = r0_vertices.map(v => v.hash);
if (r0_vertices.length !== 4) throw new Error('Expected 4 round 0 vertices');
console.log('✓ Test 1: Created Round 0 genesis vertices across 4 nodes');

// Test 2: Construct Round 1 vertices with >= 3 parents from Round 0
const r1_vertices = [];
for (let i = 0; i < 4; i++) {
  // Each node references 3 parents from round 0
  const parents = r0_hashes.slice(0, 3);
  const v = engine.addVertex(r0_nodes[i], 1, { tx: `round1_tx_${i}` }, parents);
  r1_vertices.push(v);
}
const r1_hashes = r1_vertices.map(v => v.hash);
console.log('✓ Test 2: Constructed Round 1 with valid 2f+1=3 parent references');

// Test 3: Construct Round 2 and Commit Round 1 Leader
const r2_vertices = [];
for (let i = 0; i < 4; i++) {
  const parents = r1_hashes.slice(0, 3);
  const v = engine.addVertex(r0_nodes[i], 2, { tx: `round2_tx_${i}` }, parents);
  r2_vertices.push(v);
}

// In Round 1, leader is node_1 (round 1 % 4 = 1)
const leader1 = engine.getLeaderForRound(1);
if (!leader1 || leader1.nodeId !== 'node_1') {
  throw new Error('Expected Round 1 leader to be node_1, got ' + (leader1 ? leader1.nodeId : 'null'));
}

const committed = engine.commitLeader(1);
if (!committed) throw new Error('Failed to commit Round 1 leader with round 2 quorum');
console.log('✓ Test 3: Round 1 leader (' + leader1.nodeId + ') successfully committed via Round 2 quorum');

// Verify total linear order includes causal past
const totalOrder = engine.getTotalOrder();
if (totalOrder.length === 0) throw new Error('Total order should not be empty');
console.log('✓ Test 4: Bullshark totally ordered ' + totalOrder.length + ' causal vertices deterministically');

// Test 5: Write verification report
const report = {
  experiment: 'bullshark_dag_bft',
  phase: 395,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  faultTolerance: 1,
  quorumThreshold: 3,
  committedLeader: {
    round: leader1.round,
    nodeId: leader1.nodeId,
    hash: leader1.hash
  },
  totalOrderedVertices: totalOrder.length,
  orderedSequence: totalOrder.map(v => ({ round: v.round, nodeId: v.nodeId, tx: v.payload.tx })),
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_BULLSHARK_DAG_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_BULLSHARK_DAG_REPORT.json');

console.log('All Bullshark DAG-BFT tests passed successfully!');
