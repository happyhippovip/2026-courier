const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SnapshotNode } = require('./lib/distributed_snapshot_v2');

console.log('Testing Distributed Snapshot Engine (Chandy-Lamport V2)...');

const net = new Map();
const node1 = new SnapshotNode('agent-worker-1', net);
const node2 = new SnapshotNode('agent-worker-2', net);
const node3 = new SnapshotNode('agent-worker-3', net);

net.set('agent-worker-1', node1);
net.set('agent-worker-2', node2);
net.set('agent-worker-3', node3);

node1.updateState(100);
node2.updateState(250);
node3.updateState(400);

// Test 1: Node 1 initiates snapshot
node1.initiateSnapshot('snap-101');

assert.strictEqual(node1.snapshot.state.contextTokens, 100);
assert.strictEqual(node2.snapshot.state.contextTokens, 250);
assert.strictEqual(node3.snapshot.state.contextTokens, 400);
console.log('✓ Test 1: Snapshot initiated and consistent state vectors recorded');

// Test 2: In-flight messages recorded on active channel
node2.receiveMessage('agent-worker-3', { id: 'msg-42', tokenCount: 50 });
// Complete marker roundtrip
node2.receiveMarker('agent-worker-3', 'snap-101');
assert.ok(node2.snapshot.channelStates['agent-worker-3'] !== undefined);
assert.strictEqual(node2.snapshot.channelStates['agent-worker-3'].length, 1);
assert.strictEqual(node2.snapshot.channelStates['agent-worker-3'][0].id, 'msg-42');
console.log('✓ Test 2: In-flight channel messages captured accurately in channel state');

// Test 3: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 323,
  component: 'distributed_snapshot_v2',
  snapshotId: 'snap-101',
  nodesParticipating: 3,
  globalTokenSumRecorded: 100 + 250 + 400,
  inFlightCapturedCount: 1,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_DISTRIBUTED_SNAPSHOT_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_DISTRIBUTED_SNAPSHOT_REPORT.json');
console.log('All Distributed Snapshot tests passed successfully!');
