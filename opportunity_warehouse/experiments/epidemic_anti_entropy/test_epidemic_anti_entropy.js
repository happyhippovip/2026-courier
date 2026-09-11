const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { AntiEntropyNode } = require('./lib/epidemic_anti_entropy');

console.log('Testing Epidemic Anti-Entropy Sync Engine...');

const nodeA = new AntiEntropyNode('agent-node-a');
const nodeB = new AntiEntropyNode('agent-node-b');

// Node A has keys k1, k2
nodeA.put('k1', 'val-1');
nodeA.put('k2', 'val-2');

// Node B has keys k3, k4
nodeB.put('k3', 'val-3');
nodeB.put('k4', 'val-4');

// Test 1: Sync produces symmetric convergence
const syncRes = nodeA.syncWith(nodeB);
assert.strictEqual(syncRes.syncedKeys, 4);
assert.strictEqual(nodeA.store.size, 4);
assert.strictEqual(nodeB.store.size, 4);

assert.strictEqual(nodeA.get('k3'), 'val-3');
assert.strictEqual(nodeB.get('k1'), 'val-1');
console.log('✓ Test 1: Symmetric anti-entropy convergence verified (all 4 keys shared)');

// Test 2: Incremental sync sends only deltas
nodeA.put('k5', 'val-5'); // Only 1 new key on A
const syncRes2 = nodeA.syncWith(nodeB);
assert.strictEqual(syncRes2.itemsToB, 1);
assert.strictEqual(syncRes2.itemsToA, 0);
assert.strictEqual(nodeB.get('k5'), 'val-5');
console.log('✓ Test 2: Incremental sync transferred strictly 1 delta item');

// Test 3: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 331,
  component: 'epidemic_anti_entropy',
  totalKeysSynced: nodeA.store.size,
  eventualConsistencyVerified: true,
  deltaEfficiencyVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_EPIDEMIC_ANTI_ENTROPY_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_EPIDEMIC_ANTI_ENTROPY_REPORT.json');
console.log('All Epidemic Anti-Entropy tests passed successfully!');
