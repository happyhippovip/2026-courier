const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { MultiPaxosAcceptor, MultiPaxosLeader } = require('./lib/multi_paxos_log_stream');

console.log('Testing Multi-Paxos Log Stream Engine...');

const acceptors = [
  new MultiPaxosAcceptor('acc-0'),
  new MultiPaxosAcceptor('acc-1'),
  new MultiPaxosAcceptor('acc-2')
]; // Majority = 2

const leader = new MultiPaxosLeader('leader-alpha', acceptors);

// Test 1: Phase 1 establishes leader lease across stream
const electRes = leader.acquireLeadership(1);
assert.strictEqual(electRes.status, 'LEADER_ESTABLISHED');
assert.strictEqual(leader.isLeaderActive, true);
console.log('✓ Test 1: Phase 1 amortized leadership established');

// Test 2: Stream consecutive log slots with 1 RTT per commit
const committedSlots = [];
for (let i = 0; i < 5; i++) {
  const res = leader.appendStreamEntry({ eventId: 'event-' + i, timestamp: Date.now() });
  assert.strictEqual(res.status, 'COMMITTED');
  assert.strictEqual(res.slot, i);
  assert.strictEqual(res.roundtrips, 1);
  committedSlots.push(res);
}
assert.strictEqual(committedSlots.length, 5);
console.log('✓ Test 2: 5 streaming log slots committed with strictly 1 RTT each');

// Test 3: Verify acceptors have matching replicated logs
for (const acc of acceptors) {
  assert.strictEqual(acc.log.size, 5);
  for (let i = 0; i < 5; i++) {
    assert.strictEqual(acc.log.get(i).value.eventId, 'event-' + i);
  }
}
console.log('✓ Test 3: Log consistency verified identically across all 3 acceptors');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 339,
  component: 'multi_paxos_log_stream',
  acceptorsCount: 3,
  slotsCommitted: committedSlots.length,
  singleRoundtripStreamingVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_MULTI_PAXOS_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_MULTI_PAXOS_REPORT.json');
console.log('All Multi-Paxos Log Stream tests passed successfully!');
