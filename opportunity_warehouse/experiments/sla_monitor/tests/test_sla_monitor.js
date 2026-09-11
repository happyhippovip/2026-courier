const assert = require('assert');
const { SlaMonitor } = require('../lib/sla_monitor');

console.log('Testing SlaMonitor...');

const monitor = new SlaMonitor({ maxAcceptableLatencyMs: 200 });

// Test 1: Record successful in-SLA ping
const r1 = monitor.recordPing(45, 200);
assert.strictEqual(r1.isSuccess, true);
assert.strictEqual(r1.isWithinSla, true);

// Test 2: Record high latency SLA breach
const r2 = monitor.recordPing(350, 200);
assert.strictEqual(r2.isSuccess, true);
assert.strictEqual(r2.isWithinSla, false);

// Test 3: Record HTTP 500 error
const r3 = monitor.recordPing(50, 500, 'Internal Server Error');
assert.strictEqual(r3.isSuccess, false);
assert.strictEqual(r3.isWithinSla, false);

// Test 4: Compute metrics
const metrics = monitor.getMetrics();
assert.strictEqual(metrics.totalPings, 3);
assert.strictEqual(metrics.successfulPings, 2);
assert.strictEqual(metrics.slaCompliantPings, 1);
assert.strictEqual(metrics.uptimePct, 66.67);
assert.strictEqual(metrics.slaCompliancePct, 33.33);

console.log('All SlaMonitor tests passed (4/4)!');
