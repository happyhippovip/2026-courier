const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RaftNode } = require('./lib/raft_leader_election');

console.log('Testing Multi-Agent Raft Leader Election...');

const cluster = new Map();
const node1 = new RaftNode('node-1', cluster);
const node2 = new RaftNode('node-2', cluster);
const node3 = new RaftNode('node-3', cluster);

cluster.set('node-1', node1);
cluster.set('node-2', node2);
cluster.set('node-3', node3);

// Test 1: Node 1 starts election and achieves majority
node1.startElection();
assert.strictEqual(node1.state, 'LEADER');
assert.strictEqual(node1.currentTerm, 1);
assert.strictEqual(node1.votesReceived, 3); // node1 + node2 + node3
console.log('✓ Test 1: Node 1 elected leader with unanimous quorum (3/3 votes)');

// Test 2: Leader heartbeats maintain followers in term 1
node1.sendHeartbeat();
assert.strictEqual(node2.state, 'FOLLOWER');
assert.strictEqual(node3.state, 'FOLLOWER');
assert.strictEqual(node2.currentTerm, 1);
console.log('✓ Test 2: Leader heartbeats accepted by follower nodes');

// Test 3: Node 2 initiates election in higher term -> becomes new leader
node2.startElection(); // term 2
assert.strictEqual(node2.state, 'LEADER');
assert.strictEqual(node2.currentTerm, 2);
assert.strictEqual(node1.state, 'FOLLOWER'); // Node 1 stepped down upon discovering term 2
console.log('✓ Test 3: Leadership succession verified upon higher term election (Node 2 is new Leader)');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 303,
  component: 'raft_leader_election',
  clusterSize: 3,
  nodes: ['node-1', 'node-2', 'node-3'],
  leaderNode: 'node-2',
  term: 2,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_RAFT_ELECTION_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_RAFT_ELECTION_REPORT.json');
console.log('All Raft Leader Election tests passed successfully!');
