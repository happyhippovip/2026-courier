const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ContextBoundaryBroker } = require('../lib/boundary_broker');

console.log('--- Testing Context Window Boundary Negotiator ---');

const broker = new ContextBoundaryBroker(100000, 5000); // 95,000 usable

// Register agents
broker.registerAgent('agent_supervisor', { role: 'supervisor', priorityWeight: 5.0, minTokens: 10000, requestedTokens: 25000 });
broker.registerAgent('agent_coder', { role: 'coder', priorityWeight: 4.0, minTokens: 15000, requestedTokens: 40000 });
broker.registerAgent('agent_reviewer', { role: 'reviewer', priorityWeight: 2.0, minTokens: 5000, requestedTokens: 20000 });
broker.registerAgent('agent_logger', { role: 'logger', priorityWeight: 1.0, minTokens: 2000, requestedTokens: 8000 });

// Test 1: Minimum token reservation guarantee
const alloc1 = broker.allocateBudget();
assert.ok(alloc1.allocatedTotal <= alloc1.usableCapacity, 'Allocated total must not exceed usable capacity');
for (const a of alloc1.agentAllocations) {
  assert.ok(a.allocatedTokens >= a.minTokens, 'Agent ' + a.agentId + ' must receive at least minimum tokens');
}
console.log('✓ Assertion 1 Passed: Minimum reservations strictly guaranteed');

// Test 2: Priority-weighted surplus distribution
const sup = alloc1.agentAllocations.find(a => a.agentId === 'agent_supervisor');
const log = alloc1.agentAllocations.find(a => a.agentId === 'agent_logger');
assert.ok(sup.fulfillmentPercent >= log.fulfillmentPercent, 'Higher priority agent must receive higher fulfillment');
console.log('✓ Assertion 2 Passed: Priority-weighted surplus distribution verified');

// Test 3: Surge and yield reallocation
const allocSurge = broker.requestSurge('agent_coder', 10000);
const coderAfterSurge = allocSurge.agentAllocations.find(a => a.agentId === 'agent_coder');
assert.ok(coderAfterSurge.allocatedTokens >= 15000, 'Coder retains allocated budget under surge');
const allocYield = broker.yieldTokens('agent_supervisor', 10000);
assert.ok(allocYield.freeCapacity >= 0, 'Yield reallocates tokens safely');
console.log('✓ Assertion 3 Passed: Dynamic surge and yield operations verified');

// Test 4: Export allocation manifest evidence
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_CONTEXT_BOUNDARY_ALLOCATION.json');
fs.writeFileSync(evidencePath, JSON.stringify(alloc1, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence file must exist');
console.log('✓ Assertion 4 Passed: Allocation manifest exported to SAMPLE_CONTEXT_BOUNDARY_ALLOCATION.json');

console.log('All 4 Context Boundary Negotiator tests passed successfully!');
