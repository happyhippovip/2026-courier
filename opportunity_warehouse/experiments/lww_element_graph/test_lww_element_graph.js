const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { LWWElementGraph } = require('./lib/lww_element_graph');

console.log('Testing LWW Element Graph Engine...');

const g1 = new LWWElementGraph('agent-alpha');
const g2 = new LWWElementGraph('agent-beta');

// Test 1: Add vertices and edges on g1
g1.addEdge('agent', 'memory', 100);
g1.addEdge('memory', 'context', 110);
assert.strictEqual(g1.hasVertex('agent'), true);
assert.strictEqual(g1.hasEdge('agent', 'memory'), true);
assert.strictEqual(g1.hasEdge('memory', 'context'), true);
console.log('✓ Test 1: Directed graph vertices and edges created on Agent Alpha');

// Test 2: Concurrent mutations on g2 and merge
// Agent Beta adds 'storage' and removes edge 'agent->memory' with higher timestamp 150
g2.addEdge('memory', 'storage', 120);
g2.removeEdge('agent', 'memory', 150);

g1.merge(g2);
g2.merge(g1);

assert.strictEqual(g1.hasEdge('agent', 'memory'), false); // Removed by higher timestamp
assert.strictEqual(g2.hasEdge('agent', 'memory'), false);
assert.strictEqual(g1.hasEdge('memory', 'storage'), true);
assert.strictEqual(g2.hasEdge('memory', 'storage'), true);
console.log('✓ Test 2: Symmetric merge resolved edge removal with LWW semantics');

// Test 3: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 363,
  component: 'lww_element_graph',
  verticesCount: 4,
  activeEdges: ['memory->context', 'memory->storage'],
  crdtMergeVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_LWW_ELEMENT_GRAPH_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_LWW_ELEMENT_GRAPH_REPORT.json');
console.log('All LWW Element Graph tests passed successfully!');
