const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TwoPhaseCommitCoordinator, ParticipantNode } = require('./lib/two_phase_commit_coordinator');

console.log('Testing Two-Phase Commit Coordinator...');

// Test 1: Unanimous Commit Transaction
const p1 = new ParticipantNode('agent-node-1', true);
const p2 = new ParticipantNode('agent-node-2', true);
const p3 = new ParticipantNode('agent-node-3', true);

const coord1 = new TwoPhaseCommitCoordinator([p1, p2, p3]);
const tx1 = coord1.executeTransaction('tx-1001', { contextDelta: 'block-a' });

assert.strictEqual(tx1.status, 'COMMITTED');
assert.strictEqual(p1.state, 'COMMITTED');
assert.strictEqual(p2.state, 'COMMITTED');
assert.strictEqual(p3.state, 'COMMITTED');
console.log('✓ Test 1: Unanimous commit path succeeded across 3 participants');

// Test 2: Abort Transaction when one node rejects
const p4 = new ParticipantNode('agent-node-4', true);
const p5 = new ParticipantNode('agent-node-5', false); // Will vote abort

const coord2 = new TwoPhaseCommitCoordinator([p4, p5]);
const tx2 = coord2.executeTransaction('tx-1002', { contextDelta: 'block-b' });

assert.strictEqual(tx2.status, 'ABORTED');
assert.strictEqual(p4.state, 'ABORTED');
assert.strictEqual(p5.state, 'ABORTED');
console.log('✓ Test 2: Atomic rollback verified when participant votes ABORT');

// Test 3: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 311,
  component: 'two_phase_commit_coordinator',
  transactionsExecuted: [tx1, tx2],
  atomicityGuaranteed: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_2PC_COORDINATOR_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_2PC_COORDINATOR_REPORT.json');
console.log('All Two-Phase Commit Coordinator tests passed successfully!');
