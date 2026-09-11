const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TokenGraphMST } = require('./lib/token_graph_mst');

console.log('Testing Token Graph Minimum Spanning Tree (MST)...');

const graph = new TokenGraphMST();

// Build a graph of 5 core concepts connected by semantic distance weights
graph.addEdge('agent', 'memory', 2);
graph.addEdge('agent', 'context', 3);
graph.addEdge('context', 'memory', 1);
graph.addEdge('memory', 'storage', 4);
graph.addEdge('context', 'storage', 5);
graph.addEdge('storage', 'cloud', 2);
graph.addEdge('agent', 'cloud', 8);

const result = graph.computeMST();

// Test 1: Node and edge counts
assert.strictEqual(result.nodeCount, 5);
assert.strictEqual(result.mstEdgeCount, 4); // For 5 connected nodes, tree has 4 edges
console.log('✓ Test 1: Spanning tree edge count verified (4 edges for 5 nodes)');

// Test 2: Minimal total weight check
// Optimal edges: ('context', 'memory', 1), ('agent', 'memory', 2), ('storage', 'cloud', 2), ('memory', 'storage', 4) -> sum = 9
assert.strictEqual(result.totalWeight, 9);
console.log('✓ Test 2: Optimal minimal weight verified (totalWeight: 9)');

// Test 3: Redundancy pruning ratio
assert.ok(result.compressionRatio > 0.4);
console.log('✓ Test 3: Redundancy pruning achieved: ' + (result.compressionRatio * 100).toFixed(1) + '%');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 297,
  component: 'token_graph_mst',
  nodeCount: result.nodeCount,
  edgesBeforePruning: result.originalEdgeCount,
  edgesAfterMST: result.mstEdgeCount,
  totalMSTWeight: result.totalWeight,
  compressionRatio: result.compressionRatio,
  mstEdges: result.mstEdges,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_TOKEN_GRAPH_MST_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_TOKEN_GRAPH_MST_REPORT.json');
console.log('All Token Graph MST tests passed successfully!');
