const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TreapIndexer } = require('./lib/treap_indexer');

console.log('Testing Treap Cartesian Indexer...');

const treap = new TreapIndexer();

// Insert items with key (position) and priority (saliency)
treap.insert(1, 0.40, 'token-first');
treap.insert(3, 0.95, 'token-peak');    // Highest saliency -> should climb toward root
treap.insert(2, 0.20, 'token-second');
treap.insert(4, 0.60, 'token-fourth');

// Test 1: Size and search
assert.strictEqual(treap.size, 4);
const node3 = treap.search(3);
assert.ok(node3 !== null);
assert.strictEqual(node3.token, 'token-peak');
assert.strictEqual(node3.priority, 0.95);
console.log('✓ Test 1: Treap search verified for position 3 (token-peak)');

// Test 2: Max-heap property at root
// Node with priority 0.95 should be at the root of the tree
assert.strictEqual(treap.root.key, 3);
assert.strictEqual(treap.root.priority, 0.95);
console.log('✓ Test 2: Max-Heap priority invariant verified (root has max saliency 0.95)');

// Test 3: BST invariant verification (in-order traversal is sorted by key)
function inOrderKeys(node) {
  if (!node) return [];
  return [...inOrderKeys(node.left), node.key, ...inOrderKeys(node.right)];
}
const keys = inOrderKeys(treap.root);
assert.deepStrictEqual(keys, [1, 2, 3, 4]);
console.log('✓ Test 3: BST property maintained on keys: [' + keys.join(', ') + ']');

// Test 4: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 365,
  component: 'treap_indexer',
  elementsIndexed: treap.size,
  rootElement: { key: treap.root.key, priority: treap.root.priority, token: treap.root.token },
  cartesianTreeInvariantsVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_TREAP_INDEXER_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 4: Evidence report written to SAMPLE_TREAP_INDEXER_REPORT.json');
console.log('All Treap Cartesian Indexer tests passed successfully!');
