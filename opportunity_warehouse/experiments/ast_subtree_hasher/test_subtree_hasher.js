/**
 * test_subtree_hasher.js - Test suite for AST Subtree Hasher
 */
const assert = require('assert');
const { AstSubtreeHasher } = require('./lib/subtree_hasher');

console.log('--- Running test_subtree_hasher.js ---');

const hasher = new AstSubtreeHasher();

// Test 1: Deterministic hash generation
const nodeA = { type: 'Function', name: 'calculateTax', params: ['amount', 'rate'] };
const hash1 = hasher.computeNodeHash(nodeA);
const hash2 = hasher.computeNodeHash(nodeA);
assert.strictEqual(hash1, hash2, 'Identical nodes must yield identical hash');
assert.strictEqual(typeof hash1, 'string');
assert.strictEqual(hash1.length, 16);
console.log('✓ Test 1 Passed: Deterministic 16-char structural hash generated (' + hash1 + ')');

// Test 2: Structural collision detection for duplicates
const sampleTree = {
  type: 'Program',
  children: [
    {
      type: 'ModuleA',
      children: [
        { type: 'Interface', name: 'UserDto', params: ['id', 'email'] }
      ]
    },
    {
      type: 'ModuleB',
      children: [
        { type: 'Interface', name: 'UserDto', params: ['id', 'email'] } // Exact duplicate
      ]
    }
  ]
};

const analysis = hasher.analyzeTree(sampleTree);
assert.strictEqual(analysis.duplicateCount, 1, 'Must detect exactly 1 duplicate subtree');
assert.strictEqual(analysis.duplicates[0].name, 'UserDto');
assert.strictEqual(analysis.duplicates[0].occurrences.length, 2);
console.log('✓ Test 2 Passed: Duplicate subtree across modules successfully detected');

// Test 3: Hoisting recommendation generation
assert.strictEqual(analysis.hoistingSuggestions.length, 1);
assert.ok(analysis.hoistingSuggestions[0].recommendation.includes('Hoist structural block "UserDto"'));
console.log('✓ Test 3 Passed: Actionable hoisting recommendations generated');

// Test 4: Trees with zero duplicates pass cleanly
const cleanTree = {
  type: 'Program',
  children: [
    { type: 'Function', name: 'alpha', params: [] },
    { type: 'Function', name: 'beta', params: [] }
  ]
};
const cleanRes = hasher.analyzeTree(cleanTree);
assert.strictEqual(cleanRes.duplicateCount, 0, 'Clean tree must have 0 duplicates');
console.log('✓ Test 4 Passed: Trees with unique nodes pass without false positives');

console.log('ALL 4 TESTS PASSED IN test_subtree_hasher.js\n');
