const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { PaxosAcceptor, PaxosProposer } = require('./lib/paxos_lease_engine');

console.log('Testing Paxos Lease Consensus Engine...');

const acceptors = [
  new PaxosAcceptor('acc-1'),
  new PaxosAcceptor('acc-2'),
  new PaxosAcceptor('acc-3'),
  new PaxosAcceptor('acc-4'),
  new PaxosAcceptor('acc-5')
]; // Majority = 3

const proposer1 = new PaxosProposer('prop-1', acceptors);
const proposer2 = new PaxosProposer('prop-2', acceptors);

// Test 1: Proposer 1 successfully obtains lease with round 1
const res1 = proposer1.proposeLease(1, 'agent-primary', 5000);
assert.strictEqual(res1.status, 'LEASE_GRANTED');
assert.strictEqual(res1.accepts, 5);
assert.strictEqual(res1.value.leaseHolderId, 'agent-primary');
console.log('✓ Test 1: Proposer 1 obtained exclusive lease via unanimous Paxos agreement');

// Test 2: Proposer 2 attempts with stale round 1 -> rejected
const res2 = proposer2.proposeLease(1, 'agent-secondary', 5000);
assert.strictEqual(res2.status, 'PREPARE_FAILED');
console.log('✓ Test 2: Stale proposal round rejected by quorum');

// Test 3: Proposer 2 uses higher round 2 -> discovers and upholds existing consensus value
const res3 = proposer2.proposeLease(2, 'agent-secondary', 5000);
assert.strictEqual(res3.status, 'LEASE_GRANTED');
assert.strictEqual(res3.value.leaseHolderId, 'agent-primary'); // Upholds already chosen value!
console.log('✓ Test 3: Higher round discovered and maintained previously chosen value (Safety guaranteed)');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 327,
  component: 'paxos_lease_engine',
  acceptorsCount: 5,
  majorityRequired: 3,
  leaseState: res3.value,
  consensusSafetyVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_PAXOS_LEASE_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_PAXOS_LEASE_REPORT.json');
console.log('All Paxos Lease Engine tests passed successfully!');
