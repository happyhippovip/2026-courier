const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ConsistentHashRing } = require('./lib/consistent_hash_ring');

console.log('Testing Consistent Hash Ring & Partition Rebalancer...');

const ring = new ConsistentHashRing(32);

ring.addNode('node-alpha');
ring.addNode('node-beta');
ring.addNode('node-gamma');

// Test 1: Node ring size verification
assert.strictEqual(ring.ring.length, 3 * 32);
console.log('✓ Test 1: Ring initialized with 3 physical nodes and 96 virtual replicas');

// Test 2: Consistent key mapping
const testKeys = [];
for (let i = 0; i < 100; i++) testKeys.push('context-partition-' + i);

const mappingBefore = new Map();
for (const k of testKeys) {
  mappingBefore.set(k, ring.getNode(k));
}

// Ensure all 3 nodes receive some partition allocation
const countsBefore = { 'node-alpha': 0, 'node-beta': 0, 'node-gamma': 0 };
for (const node of mappingBefore.values()) {
  countsBefore[node]++;
}
assert.ok(countsBefore['node-alpha'] > 15);
assert.ok(countsBefore['node-beta'] > 15);
assert.ok(countsBefore['node-gamma'] > 15);
console.log('✓ Test 2: Uniform distribution across 3 nodes verified', countsBefore);

// Test 3: Add 4th node and verify minimal churn (rebalancing)
ring.addNode('node-delta');
let reallocatedCount = 0;
for (const k of testKeys) {
  const newOwner = ring.getNode(k);
  if (newOwner !== mappingBefore.get(k)) {
    reallocatedCount++;
    assert.strictEqual(newOwner, 'node-delta'); // Only new node should take keys
  }
}
const churnRate = reallocatedCount / testKeys.length;
assert.ok(churnRate <= 0.35); // Theoretical 1/4 = 25% churn
console.log('✓ Test 3: Minimal churn rebalancing verified: ' + (churnRate * 100).toFixed(1) + '% reallocated to node-delta');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 307,
  component: 'consistent_hash_ring',
  physicalNodes: 4,
  virtualReplicasPerNode: 32,
  totalVirtualNodes: ring.ring.length,
  totalKeysTested: testKeys.length,
  churnRateOnExpansion: churnRate,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_CONSISTENT_HASH_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_CONSISTENT_HASH_REPORT.json');
console.log('All Consistent Hash Ring tests passed successfully!');
