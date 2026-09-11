const { TuskConsensusEngine } = require('../lib/tusk_consensus_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Tusk High-Throughput Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const engine = new TuskConsensusEngine(nodes, 1);

// Wave 0 spans rounds 0, 1, 2
// Round 0: Propose (Leader wave 0 is node_0 at round 0)
const r0 = nodes.map(n => engine.addVertex(n, 0, `batch_${n}_r0`, []));
const r0_hashes = r0.map(v => v.hash);
console.log('✓ Test 1: Created Round 0 propose vertices');

// Round 1: Vote
const r1 = nodes.map(n => engine.addVertex(n, 1, `batch_${n}_r1`, r0_hashes.slice(0, 3)));
const r1_hashes = r1.map(v => v.hash);
console.log('✓ Test 2: Created Round 1 vote vertices with quorum parents');

// Round 2: Certify
const r2 = nodes.map(n => engine.addVertex(n, 2, `batch_${n}_r2`, r1_hashes.slice(0, 3)));
console.log('✓ Test 3: Created Round 2 certify vertices');

// Commit Wave 0 Leader
const leaderWave0 = engine.getWaveLeader(0);
if (!leaderWave0 || leaderWave0.nodeId !== 'node_0') {
  throw new Error('Expected Wave 0 leader to be node_0');
}

const committed = engine.tryCommitWaveLeader(0);
if (!committed) throw new Error('Failed to commit Wave 0 leader via Round 2 certification quorum');
console.log('✓ Test 4: Successfully committed Wave 0 leader (' + leaderWave0.nodeId + ') asynchronously');

const order = engine.getLinearOrder();
if (order.length === 0) throw new Error('Linear order should not be empty');
console.log('✓ Test 5: Tusk ordered ' + order.length + ' causal vertices deterministically');

// Test 6: Write verification report
const report = {
  experiment: 'tusk_consensus_engine',
  phase: 403,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  quorum: 3,
  waveCommitted: 0,
  leaderNode: leaderWave0.nodeId,
  orderedVerticesCount: order.length,
  orderedVertices: order,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_TUSK_CONSENSUS_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 6: Evidence report written to SAMPLE_TUSK_CONSENSUS_REPORT.json');

console.log('All Tusk Consensus Engine tests passed successfully!');
