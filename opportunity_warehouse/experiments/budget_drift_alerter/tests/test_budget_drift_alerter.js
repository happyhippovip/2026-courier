const assert = require('assert');
const { BudgetDriftAlerter } = require('../lib/budget_drift_alerter');

console.log('Testing BudgetDriftAlerter...');

const alerter = new BudgetDriftAlerter({ maxTokensPerTurn: 4000, maxDriftPct: 20 });

// Test 1: Normal turn within budget
const r1 = alerter.evaluateTurn(2500, 2400);
assert.strictEqual(r1.requiresAlert, false);
assert.strictEqual(r1.severity, 'OK');
assert.strictEqual(r1.alertPayload, null);

// Test 2: Drift exceeded but within hard cap
const r2 = alerter.evaluateTurn(3000, 2000); // +50% drift
assert.strictEqual(r2.isDriftExceeded, true);
assert.strictEqual(r2.exceedsHardBudget, false);
assert.strictEqual(r2.requiresAlert, true);
assert.strictEqual(r2.severity, 'WARNING');

// Test 3: Hard cap exceeded
const r3 = alerter.evaluateTurn(4500, 4200);
assert.strictEqual(r3.exceedsHardBudget, true);
assert.strictEqual(r3.requiresAlert, true);

// Test 4: Critical double breach
const r4 = alerter.evaluateTurn(5000, 3000);
assert.strictEqual(r4.severity, 'CRITICAL');
assert.ok(r4.alertPayload.title.includes('CRITICAL'));

console.log('All BudgetDriftAlerter tests passed (4/4)!');
