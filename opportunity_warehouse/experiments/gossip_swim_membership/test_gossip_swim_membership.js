const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { GossipNode } = require('./lib/gossip_swim_membership');

console.log('Testing SWIM Gossip Membership & Failure Detector...');

const cluster = new Map();
const nodeA = new GossipNode('agent-node-a', cluster);
const nodeB = new GossipNode('agent-node-b', cluster);
const nodeC = new GossipNode('agent-node-c', cluster);

cluster.set('agent-node-a', nodeA);
cluster.set('agent-node-b', nodeB);
cluster.set('agent-node-c', nodeC);

// Test 1: Membership dissemination
nodeB.join(nodeA);
nodeC.join(nodeA);

assert.strictEqual(nodeA.membership.has('agent-node-b'), true);
assert.strictEqual(nodeA.membership.has('agent-node-c'), true);
console.log('✓ Test 1: Cluster membership gossip initialization verified');

// Test 2: Direct health check
const res1 = nodeA.checkHealth('agent-node-b', ['agent-node-c']);
assert.strictEqual(res1.state, 'ALIVE');
assert.strictEqual(res1.method, 'DIRECT');
console.log('✓ Test 2: Direct ping health check successful');

// Test 3: Failure detection on simulated crash
nodeB.isUnreachable = true; // Simulate crash
const res2 = nodeA.checkHealth('agent-node-b', ['agent-node-c']);
assert.strictEqual(res2.state, 'SUSPECT');
assert.strictEqual(res2.method, 'FAILED');
console.log('✓ Test 3: Indirect ping failed; nodeB marked SUSPECT');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 315,
  component: 'gossip_swim_membership',
  clusterSize: 3,
  membershipStates: Object.fromEntries(nodeA.membership),
  failureDetectionVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_GOSSIP_SWIM_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_GOSSIP_SWIM_REPORT.json');
console.log('All SWIM Gossip Membership tests passed successfully!');
