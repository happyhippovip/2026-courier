/**
 * test_budget_reallocator.js - Test suite for Dynamic Budget Reallocator
 */
const assert = require('assert');
const { DynamicBudgetReallocator } = require('./lib/budget_reallocator');

console.log('--- Running test_budget_reallocator.js ---');

const reallocator = new DynamicBudgetReallocator({ globalCeilingTokens: 10000 });

// Test 1: Harvest surplus and transfer to hungry high-priority task
const tasks1 = [
  { id: 'system_prompt', priority: 1, allocatedBudget: 3000, consumedTokens: 800 }, // surplus 2200
  { id: 'complex_reasoning', priority: 5, allocatedBudget: 4000, consumedTokens: 4000 } // starved, critical
];

const res1 = reallocator.balanceBudgets(tasks1);
assert.strictEqual(res1.summary.withinCeiling, true, 'Must stay within ceiling');
assert.ok(res1.summary.surplusHarvested >= 2200, 'Surplus harvested correctly');

const reasoningTask = res1.tasks.find(t => t.id === 'complex_reasoning');
assert.ok(reasoningTask.reallocatedBudget > 4000, 'Reasoning task should receive additional budget');
console.log('✓ Test 1 Passed: Surplus harvested and reallocated to high-priority task (+' + reasoningTask.deltaTokens + ' tokens)');

// Test 2: Global ceiling never breached
const greedyTasks = [
  { id: 'task_a', priority: 5, allocatedBudget: 6000, consumedTokens: 6000 },
  { id: 'task_b', priority: 5, allocatedBudget: 6000, consumedTokens: 6000 }
];
const res2 = reallocator.balanceBudgets(greedyTasks);
assert.ok(res2.summary.totalFinalAllocated <= 10000, 'Final allocated must never exceed 10,000 ceiling');
assert.strictEqual(res2.summary.withinCeiling, true, 'withinCeiling must be true');
console.log('✓ Test 2 Passed: Hard ceiling strictly enforced under heavy allocation pressure (' + res2.summary.totalFinalAllocated + ' <= 10000)');

// Test 3: Respects minBudget bounds
const lowTask = [
  { id: 'low_task', priority: 1, minBudget: 400, allocatedBudget: 2000, consumedTokens: 50 }
];
const res3 = reallocator.balanceBudgets(lowTask);
assert.ok(res3.tasks[0].reallocatedBudget >= 400, 'Must not trim below minBudget 400');
console.log('✓ Test 3 Passed: Subtask minimum budget floor respected');

// Test 4: Stable allocation when all tasks are balanced
const balancedTasks = [
  { id: 'task_1', priority: 3, allocatedBudget: 2000, consumedTokens: 2000 },
  { id: 'task_2', priority: 3, allocatedBudget: 2000, consumedTokens: 2000 }
];
const res4 = reallocator.balanceBudgets(balancedTasks);
assert.strictEqual(res4.summary.withinCeiling, true);
assert.strictEqual(res4.summary.surplusHarvested, 0, 'No surplus when perfectly balanced');
console.log('✓ Test 4 Passed: Zero-drift behavior on balanced task sets');

console.log('ALL 4 TESTS PASSED IN test_budget_reallocator.js\n');
