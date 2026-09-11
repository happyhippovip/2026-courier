const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { DependencyGraph } = require('../lib/dependency_graph');

console.log('--- Testing AST Context Dependency Graph Extractor ---');

const graph = new DependencyGraph();

// 1. Add Context Nodes
graph.addNode('sys_core', { label: 'System Core Prompt', type: 'system', tokens: 1200, priority: 'critical' });
graph.addNode('rule_safety', { label: 'Safety & Sandbox Gates', type: 'rules', tokens: 450, priority: 'critical' });
graph.addNode('tool_browser', { label: 'Browser Tool Schema', type: 'tool', tokens: 850, priority: 'medium' });
graph.addNode('tool_db', { label: 'Database Tool Schema', type: 'tool', tokens: 620, priority: 'medium' });
graph.addNode('user_persona', { label: 'User Persona Profile', type: 'persona', tokens: 300, priority: 'low' });
graph.addNode('conv_history_turn1', { label: 'Historical Turn 1', type: 'history', tokens: 780, priority: 'low' });
graph.addNode('conv_history_turn2', { label: 'Historical Turn 2', type: 'history', tokens: 920, priority: 'low' });

// 2. Add Dependencies (from -> to means 'from' depends on / requires 'to')
graph.addDependency('rule_safety', 'sys_core');
graph.addDependency('tool_browser', 'rule_safety');
graph.addDependency('tool_db', 'rule_safety');
graph.addDependency('conv_history_turn2', 'conv_history_turn1');

// Test 1: Cycle-free DAG verification
assert.strictEqual(graph.hasCycle(), false, 'Graph must be an acyclic DAG');
const topoOrder = graph.topologicalSort();
assert.ok(topoOrder.length === 7, 'Topological sort must include all 7 nodes');
console.log('✓ Assertion 1 Passed: Cycle-free DAG verified and topologically sorted');

// Test 2: In-degree and out-degree metrics
const report = graph.generateReport();
const sysCoreMetrics = report.nodeMetrics.find(n => n.id === 'sys_core');
assert.strictEqual(sysCoreMetrics.inDegree, 1, 'sys_core must have inDegree 1 (rule_safety depends on it)');
assert.strictEqual(sysCoreMetrics.outDegree, 0, 'sys_core has outDegree 0 (depends on nothing)');
console.log('✓ Assertion 2 Passed: In-degree and out-degree centrality accurate');

// Test 3: Pruning candidates identification without breaking dependencies
const candidates = graph.getPruningCandidates();
assert.ok(candidates.length > 0, 'Must identify pruning candidates');
const candidateIds = candidates.map(c => c.id);
assert.ok(!candidateIds.includes('sys_core'), 'sys_core must never be prunable');
assert.ok(!candidateIds.includes('rule_safety'), 'rule_safety must not be prunable (depended on by tools)');
assert.ok(candidateIds.includes('conv_history_turn2'), 'conv_history_turn2 is a leaf and safely prunable');
console.log('✓ Assertion 3 Passed: Safe leaf pruning identified without ancestor breakage');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_AST_DEPENDENCY_GRAPH.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_AST_DEPENDENCY_GRAPH.json');

console.log('All 4 Dependency Graph tests passed successfully!');
