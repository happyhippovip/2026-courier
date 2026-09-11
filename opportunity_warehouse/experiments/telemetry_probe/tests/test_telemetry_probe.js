const assert = require('assert');
const path = require('path');
const { inspectSystemHealth } = require('../lib/health_probe');

console.log('Running Telemetry Health Probe Tests...');

// Test 1: Standard inspection in current workspace
const health1 = inspectSystemHealth();
assert.strictEqual(typeof health1.probe_id, 'string', 'Probe ID must be string');
assert.strictEqual(typeof health1.checks.runtime.node_version, 'string', 'Node version must be present');
assert.strictEqual(health1.checks.runtime.status, 'OK', 'Runtime status must be OK');
console.log('  [PASS] Test 1: Standard health inspection metrics retrieved');

// Test 2: Directory accessibility validation
assert.ok(health1.checks.directories.opportunity_warehouse, 'opportunity_warehouse must be checked');
assert.strictEqual(health1.checks.directories.opportunity_warehouse.accessible, true, 'opportunity_warehouse must be accessible');
console.log('  [PASS] Test 2: Directory accessibility confirmed');

// Test 3: Active leases validation
assert.strictEqual(typeof health1.checks.leases.active_leases_count, 'number', 'Lease count must be numeric');
console.log('  [PASS] Test 3: Leases check verified');

// Test 4: Missing directory degradation check
const healthDegraded = inspectSystemHealth({ rootDir: 'C:/NonExistentPath_Test_123' });
assert.strictEqual(healthDegraded.overall_status, 'DEGRADED', 'Missing root path must return DEGRADED status');
console.log('  [PASS] Test 4: Graceful degradation on missing directory verified');

console.log('ALL 4 TELEMETRY HEALTH PROBE TESTS PASSED DETERMINISTICALLY!');
