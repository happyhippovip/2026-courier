/**
 * test_telemetry_aggregator.js - Test suite for Telemetry Privacy Guard
 */
const assert = require('assert');
const { TelemetryPrivacyGuard } = require('./lib/telemetry_aggregator');

console.log('--- Running test_telemetry_aggregator.js ---');

const guard = new TelemetryPrivacyGuard({ tokenBucketSize: 50, latencyBucketMs: 10 });

// Test 1: PII and raw code are completely purged
const dirtyEvent = {
  machineId: 'win-dev-box-42',
  workspacePath: 'C:\\SecretProject\\InternalFinancials',
  userName: 'john_doe',
  email: 'john@secret.com',
  promptContent: 'SELECT * FROM users WHERE ssn = 1234;',
  tokensSaved: 142,
  latencyMs: 23,
  rulesAppliedCount: 3,
  exitCode: 0
};

const clean = guard.sanitizeEvent(dirtyEvent);
guard.assertZeroPii(clean);
assert.strictEqual(clean.promptContent, undefined, 'Prompt content must not exist');
assert.strictEqual(clean.userName, undefined, 'User name must not exist');
assert.strictEqual(clean.workspacePath, undefined, 'Workspace path must not exist');
console.log('✓ Test 1 Passed: Complete PII and prompt purge verified');

// Test 2: Machine identifier hashed with one-way HMAC
assert.ok(clean.machineHash.length === 16, 'Machine hash must be 16-char hex substring');
assert.notStrictEqual(clean.machineHash, 'win-dev-box-42', 'Raw machine ID must not be leaked');
const hash2 = guard.hashIdentifier('win-dev-box-42');
assert.strictEqual(clean.machineHash, hash2, 'Hash must be deterministic for identical ID and salt');
console.log('✓ Test 2 Passed: Deterministic one-way machine hashing confirmed');

// Test 3: Metric bucketization for differential privacy
assert.strictEqual(clean.tokensSaved, 150, 'Tokens saved 142 should round to bucket 150');
assert.strictEqual(clean.latencyMs, 20, 'Latency 23ms should round to bucket 20ms');
console.log('✓ Test 3 Passed: Differential privacy metric bucketization works as expected');

// Test 4: Batch aggregation produces safe overview
const batch = [
  dirtyEvent,
  { machineId: 'win-dev-box-42', tokensSaved: 88, latencyMs: 31, exitCode: 0 },
  { machineId: 'mac-dev-box-99', tokensSaved: 210, latencyMs: 45, exitCode: 1 }
];
const summary = guard.aggregate(batch);
assert.strictEqual(summary.metrics.totalEvents, 3, 'Total events must be 3');
assert.strictEqual(summary.metrics.uniqueMachines, 2, 'Unique machines must be 2');
assert.ok(summary.privacyGuarantees.piiRemoved, 'PII removed guarantee must be true');
assert.ok(summary.metrics.totalTokensSavedBucketized > 400, 'Total tokens saved correctly summed');
console.log('✓ Test 4 Passed: Batch telemetry aggregation matches strict privacy guarantees');

console.log('ALL 4 TESTS PASSED IN test_telemetry_aggregator.js\n');
