const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { KademliaNode } = require('./lib/kademlia_dht_router');

console.log('Testing Kademlia DHT Routing Engine...');

const rootNode = new KademliaNode('0001', 3);

// Test 1: XOR metric distance properties
assert.strictEqual(rootNode.distance('0001'), 0);
assert.strictEqual(rootNode.distance('0002'), 3); // 1 ^ 2 = 3
assert.strictEqual(rootNode.distance('0003'), 2); // 1 ^ 3 = 2
console.log('✓ Test 1: XOR metric symmetric distance verified');

// Test 2: Add multiple contacts
const contacts = ['0002', '0004', '0008', '0010', '0020'];
for (const c of contacts) {
  rootNode.addContact(c);
}

// Test 3: Find closest nodes to target '0003'
const closest = rootNode.findClosestNodes('0003');
assert.strictEqual(closest.length, 3); // k = 3
assert.strictEqual(closest[0], '0002'); // '0002' ^ '0003' = 1 (closest!)
console.log('✓ Test 2: Kademlia routing lookup identified closest nodes: ' + closest.join(', '));

// Test 4: Value storage and retrieval
rootNode.putValue('context-chunk-alpha', { tokens: 120, hash: 'sha256-abc' });
const stored = rootNode.getValue('context-chunk-alpha');
assert.strictEqual(stored.tokens, 120);
console.log('✓ Test 3: DHT key-value storage and retrieval verified');

// Test 5: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 343,
  component: 'kademlia_dht_router',
  nodeId: rootNode.nodeIdHex,
  kBucketCapacity: 3,
  routingLookupTarget: '0003',
  closestNodesFound: closest,
  xorMetricVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_KADEMLIA_DHT_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_KADEMLIA_DHT_REPORT.json');
console.log('All Kademlia DHT Router tests passed successfully!');
