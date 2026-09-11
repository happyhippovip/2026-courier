const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { VectorClock } = require('../lib/vector_clock');

// Test 1: Vector clock ticking and message passing
const clockA = new VectorClock('agent_A');
const clockB = new VectorClock('agent_B');

clockA.tick(); // A: { A: 1 }
const msgFromA = clockA.send(); // A: { A: 2 }
assert.strictEqual(clockA.clock.agent_A, 2);

clockB.receive(msgFromA); // B updates: max(A:2, B:0) + tick -> { A: 2, B: 1 }
assert.strictEqual(clockB.clock.agent_A, 2);
assert.strictEqual(clockB.clock.agent_B, 1);
console.log('✓ Test 1: Causal message passing clock propagation verified');

// Test 2: Identifies happens-before accurately
const relAB = VectorClock.compare(msgFromA, clockB);
assert.strictEqual(relAB, 'HAPPENS_BEFORE', 'msgFromA happened before clockB received it');
console.log('✓ Test 2: Happens-before relation accurately detected');

// Test 3: Detects concurrent events
const clockC1 = new VectorClock('agent_C');
const clockC2 = new VectorClock('agent_D');
clockC1.tick(); // { C: 1 }
clockC2.tick(); // { D: 1 }

const relConcurrent = VectorClock.compare(clockC1, clockC2);
assert.strictEqual(relConcurrent, 'CONCURRENT', 'Independent events without communication must be CONCURRENT');
console.log('✓ Test 3: Concurrent event detection confirmed');

// Test 4: Conflict resolution on concurrent events and evidence write
const event1 = {
  eventId: 'evt_update_01',
  agentId: 'agent_C',
  action: 'UPDATE_CONTEXT_BUDGET',
  clock: clockC1
};
const event2 = {
  eventId: 'evt_update_02',
  agentId: 'agent_D',
  action: 'UPDATE_CONTEXT_BUDGET',
  clock: clockC2
};

const resolution = VectorClock.resolveConflict(event1, event2);
assert.ok(resolution.winner, 'Must select a deterministic winner');
assert.strictEqual(resolution.winner.agentId, 'agent_C', 'agent_C comes before agent_D lexicographically');
console.log('✓ Test 4: Conflict deterministically resolved (' + resolution.winner.agentId + ' won via ' + resolution.reason + ')');

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_VECTOR_CLOCK_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  messageExchange: {
    agentA: clockA.clock,
    agentB: clockB.clock
  },
  concurrencyEvaluation: {
    relation: relConcurrent,
    resolutionWinner: resolution.winner.eventId,
    resolutionReason: resolution.reason
  }
}, null, 2), 'utf8');
console.log('✓ Evidence report written to SAMPLE_VECTOR_CLOCK_REPORT.json');

console.log('All Vector Clock Engine tests passed successfully!');
