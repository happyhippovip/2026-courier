const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { PriorityInversionArbiter } = require('../lib/priority_arbiter');

const arbiter = new PriorityInversionArbiter();

// Register agents: Low (priority 1), Medium (priority 5), High (priority 10)
const agentLow = arbiter.registerAgent('agent_low', 1);
const agentMed = arbiter.registerAgent('agent_med', 5);
const agentHigh = arbiter.registerAgent('agent_high', 10);

// Test 1: Low-priority agent acquires lock uncontended
const acq1 = arbiter.acquireLock('agent_low', 'context_buffer_lock');
assert.strictEqual(acq1.acquired, true);
assert.strictEqual(agentLow.effectivePriority, 1);
console.log('✓ Test 1: Low-priority agent acquired lock uncontended');

// Test 2: High-priority agent requests same lock -> triggers priority inheritance
const acq2 = arbiter.acquireLock('agent_high', 'context_buffer_lock');
assert.strictEqual(acq2.acquired, false, 'High priority agent must block');
assert.strictEqual(acq2.elevated, true, 'Priority inheritance should trigger');
assert.strictEqual(agentLow.effectivePriority, 10, 'Low-priority agent must inherit priority 10');
console.log('✓ Test 2: Low-priority holder dynamically elevated to priority 10 (preventing medium preemption)');

// Test 3: Low-priority agent releases lock -> demoted to base priority, high-priority waiter acquires lock
const rel1 = arbiter.releaseLock('agent_low', 'context_buffer_lock');
assert.strictEqual(rel1.released, true);
assert.strictEqual(rel1.nextHolderId, 'agent_high');
assert.strictEqual(agentLow.effectivePriority, 1, 'Low-priority agent must return to base priority 1');
assert.strictEqual(agentHigh.acquiredLocks.size, 1, 'High-priority agent now holds the lock');
console.log('✓ Test 3: Lock released; low-priority demoted back to 1 and high-priority acquired lock');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_PRIORITY_ARBITER_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  elevationEvents: arbiter.elevationEvents,
  finalState: {
    agentLow: { base: agentLow.basePriority, effective: agentLow.effectivePriority },
    agentHigh: { base: agentHigh.basePriority, effective: agentHigh.effectivePriority }
  }
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_PRIORITY_ARBITER_REPORT.json');

console.log('All Priority Inversion Arbiter tests passed successfully!');
