const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TopologicalDagSorter } = require('../lib/dag_sorter');

const sorter = new TopologicalDagSorter();

// Setup DAG nodes with non-linear dependencies
sorter.addNode('verify_credentials', [], { action: 'Verify HMAC tokens' });
sorter.addNode('fetch_account_balance', ['verify_credentials'], { action: 'Query database ledger' });
sorter.addNode('acquire_memory_lock', ['verify_credentials'], { action: 'Claim agent mutex' });
sorter.addNode('settle_order', ['fetch_account_balance', 'acquire_memory_lock'], { action: 'Execute settlement transaction' });
sorter.addNode('release_memory_lock', ['settle_order'], { action: 'Release agent mutex' });

// Test 1: Cycle detection on valid DAG returns false
assert.strictEqual(sorter.detectCycle(), false, 'Valid DAG must have no cycles');
console.log('✓ Assertion 1 Passed: Valid acyclic DAG verified');

// Test 2: Cycle detection on cyclic graph returns true
const cyclicSorter = new TopologicalDagSorter();
cyclicSorter.addNode('A', ['B'], {});
cyclicSorter.addNode('B', ['A'], {});
assert.strictEqual(cyclicSorter.detectCycle(), true, 'Cyclic graph must be detected');
console.log('✓ Assertion 2 Passed: Cyclic dependency detected correctly');

// Test 3: Topological sort yields correct causal ordering
const sorted = sorter.topologicalSort();
assert.strictEqual(sorted.length, 5, 'All 5 nodes must be included');
const nodeIndices = new Map();
sorted.forEach((n, idx) => nodeIndices.set(n.id, idx));

// Invariant: dependencies must appear before dependents
assert.ok(nodeIndices.get('verify_credentials') < nodeIndices.get('fetch_account_balance'));
assert.ok(nodeIndices.get('verify_credentials') < nodeIndices.get('acquire_memory_lock'));
assert.ok(nodeIndices.get('fetch_account_balance') < nodeIndices.get('settle_order'));
assert.ok(nodeIndices.get('acquire_memory_lock') < nodeIndices.get('settle_order'));
assert.ok(nodeIndices.get('settle_order') < nodeIndices.get('release_memory_lock'));
console.log('✓ Assertion 3 Passed: Topological sort verified causal ordering strictly');

// Test 4: Format causal prompt and export evidence
const promptContext = sorter.formatCausalPrompt(sorted);
assert.ok(promptContext.includes('--- CAUSAL EXECUTION TRACE ---'), 'Prompt must contain trace header');

const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_TOPOLOGICAL_DAG_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  totalNodes: sorted.length,
  sortedSequence: sorted.map(s => s.id),
  causalPromptSnippet: promptContext,
  acyclicVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_TOPOLOGICAL_DAG_REPORT.json');

console.log('All 4 Topological DAG Sorter tests passed successfully!');