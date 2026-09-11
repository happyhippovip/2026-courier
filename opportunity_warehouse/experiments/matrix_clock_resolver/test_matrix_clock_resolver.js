const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { MatrixClockNode } = require('./lib/matrix_clock_resolver');

console.log('Testing Matrix Clock Resolver Engine...');

const node0 = new MatrixClockNode('agent-0', 0, 3);
const node1 = new MatrixClockNode('agent-1', 1, 3);
const node2 = new MatrixClockNode('agent-2', 2, 3);

// Test 1: Local events increment diagonal element
node0.logEvent('event-0-a');
node0.logEvent('event-0-b');
assert.strictEqual(node0.matrix[0][0], 2);
console.log('✓ Test 1: Node 0 diagonal timestamp advanced to 2');

// Test 2: Message propagation from node 0 to node 1
node1.receiveMessage(0, node0.matrix);
assert.strictEqual(node1.matrix[1][0], 2); // Node 1 knows Node 0 is at 2
console.log('✓ Test 2: Matrix clock propagation from Node 0 to Node 1 verified');

// Test 3: Propagation from node 1 to node 2
node2.receiveMessage(1, node1.matrix);
assert.strictEqual(node2.matrix[2][0], 2); // Node 2 now also knows Node 0 is at 2

// Test 4: Garbage collection threshold check
// Both node 0, 1, and 2 know node 0 reached at least 2
const gcThreshold = node2.getGarbageCollectionThreshold(0);
assert.strictEqual(gcThreshold, 2);
console.log('✓ Test 4: Distributed garbage collection threshold calculated accurately (threshold: 2)');

// Test 5: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 335,
  component: 'matrix_clock_resolver',
  nodesInCluster: 3,
  finalMatrixNode2: node2.matrix,
  gcThresholdNode0: gcThreshold,
  causalityTrackingVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_MATRIX_CLOCK_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 5: Evidence report written to SAMPLE_MATRIX_CLOCK_REPORT.json');
console.log('All Matrix Clock Resolver tests passed successfully!');
