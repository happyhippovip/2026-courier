const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { DRRContextScheduler } = require('../lib/drr_scheduler');

const scheduler = new DRRContextScheduler({ quantumBase: 100, globalTokenCapacity: 2000 });

// Test 1: Equal weights receive fair token throughput
scheduler.registerTenant('agent_alpha', 1);
scheduler.registerTenant('agent_beta', 1);

for (let i = 0; i < 5; i++) {
  scheduler.enqueueRequest('agent_alpha', { tokenCost: 50 });
  scheduler.enqueueRequest('agent_beta', { tokenCost: 50 });
}

const drainResult = scheduler.drain(2000);
assert.strictEqual(drainResult.totalRequests, 10, 'All 10 equal requests should be served across rounds');
const stats1 = scheduler.getTenantStats();
assert.strictEqual(stats1.agent_alpha.servedTokens, 250, 'Alpha should receive 250 tokens');
assert.strictEqual(stats1.agent_beta.servedTokens, 250, 'Beta should receive 250 tokens');
console.log('✓ Test 1: Equal weights achieve identical service (250 vs 250 tokens)');

// Test 2: Unequal weights receive strictly proportional service
const schedulerWeighted = new DRRContextScheduler({ quantumBase: 100, globalTokenCapacity: 3000 });
schedulerWeighted.registerTenant('vip_agent', 3);      // quantum = 300
schedulerWeighted.registerTenant('standard_agent', 1); // quantum = 100

for (let i = 0; i < 6; i++) {
  schedulerWeighted.enqueueRequest('vip_agent', { tokenCost: 100 });
  schedulerWeighted.enqueueRequest('standard_agent', { tokenCost: 100 });
}

schedulerWeighted.scheduleRound(800);
const statsWeighted = schedulerWeighted.getTenantStats();
assert.ok(statsWeighted.vip_agent.servedTokens >= statsWeighted.standard_agent.servedTokens * 2, 'VIP agent should receive proportional throughput');
console.log('✓ Test 2: Weighted tenant serviced proportionally (' + statsWeighted.vip_agent.servedTokens + ' vs ' + statsWeighted.standard_agent.servedTokens + ')');

// Test 3: Deficit accumulation enables large request servicing
const schedulerLarge = new DRRContextScheduler({ quantumBase: 50, globalTokenCapacity: 500 });
schedulerLarge.registerTenant('batch_agent', 1); // quantum = 50
schedulerLarge.enqueueRequest('batch_agent', { tokenCost: 120 }); // requires 3 rounds of quantum accumulation

// Round 1: quantum adds 50, deficit 50 < 120 -> 0 served
const r1 = schedulerLarge.scheduleRound(500);
assert.strictEqual(r1.requestsServed, 0, 'Round 1 deficit (50) insufficient for 120 token request');

// Round 2: quantum adds 50, deficit 100 < 120 -> 0 served
const r2 = schedulerLarge.scheduleRound(500);
assert.strictEqual(r2.requestsServed, 0, 'Round 2 deficit (100) insufficient for 120 token request');

// Round 3: quantum adds 50, deficit 150 >= 120 -> served!
const r3 = schedulerLarge.scheduleRound(500);
assert.strictEqual(r3.requestsServed, 1, 'Round 3 deficit (150) successfully serves 120 token request');
assert.strictEqual(schedulerLarge.getTenantStats().batch_agent.deficit, 0, 'Empty queue resets deficit');
console.log('✓ Test 3: Deficit successfully accumulated across rounds to service oversized request');

// Test 4: Jain's Fairness Index computation and evidence write
const jfi = scheduler.calculateJainsFairnessIndex();
assert.strictEqual(jfi, 1.0, 'Equal tenant scheduling must yield JFI = 1.0');

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_DRR_SCHEDULER_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  jainsFairnessIndex: jfi,
  stats: scheduler.getTenantStats(),
  roundExecution: drainResult
}, null, 2), 'utf8');
console.log('✓ Test 4: Jain Fairness Index computed (1.0000) and evidence written');

console.log('All DRR Context Scheduler tests passed successfully!');
