const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { DynamoCluster } = require('./lib/dynamo_quorum_replicator');

console.log('Testing Dynamo Quorum Replicator Engine...');

// N = 3, R = 2, W = 2 -> R + W = 4 > 3 (Strong consistency guaranteed)
const cluster = new DynamoCluster(['rep-1', 'rep-2', 'rep-3'], 2, 2);

// Test 1: Quorum Write
const writeRes = cluster.write('ctx-block-alpha', { content: 'symphony context data', tokens: 150 });
assert.strictEqual(writeRes.status, 'WRITE_COMMITTED');
assert.strictEqual(writeRes.written, 2);
console.log('✓ Test 1: Quorum write succeeded across W=2 replicas');

// Test 2: Quorum Read
const readRes = cluster.read('ctx-block-alpha');
assert.strictEqual(readRes.quorumMet, true);
assert.strictEqual(readRes.value.tokens, 150);
console.log('✓ Test 2: Quorum read succeeded with R=2 replicas');

// Test 3: Read Repair simulation
// Artificially plant a stale version in rep-1
cluster.replicas.get('rep-1').put('ctx-key', 'stale-value', 100, 100);
cluster.replicas.get('rep-2').put('ctx-key', 'fresh-value', 200, 200);

const repairRead = cluster.read('ctx-key');
assert.strictEqual(repairRead.value, 'fresh-value');
assert.strictEqual(repairRead.readRepairsTriggered, 1);
assert.strictEqual(cluster.replicas.get('rep-1').get('ctx-key').value, 'fresh-value'); // rep-1 repaired!
console.log('✓ Test 3: Read-repair successfully detected and synchronized stale replica');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 355,
  component: 'dynamo_quorum_replicator',
  n: 3,
  r: 2,
  w: 2,
  strongConsistencyFormulaSatisfied: true,
  readRepairVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_DYNAMO_QUORUM_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_DYNAMO_QUORUM_REPORT.json');
console.log('All Dynamo Quorum Replicator tests passed successfully!');
