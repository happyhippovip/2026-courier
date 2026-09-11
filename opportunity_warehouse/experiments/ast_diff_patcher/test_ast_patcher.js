/**
 * test_ast_patcher.js - Test suite for AST Diff-Patcher
 */
const assert = require('assert');
const { AstDiffPatcher } = require('./lib/ast_patcher');

console.log('--- Running test_ast_patcher.js ---');

const patcher = new AstDiffPatcher();

// Test 1: Successful node replacement
const initialTree = {
  type: 'Program',
  name: 'RootModule',
  children: [
    { type: 'Function', name: 'getUser', body: 'return null;' },
    { type: 'Function', name: 'deleteUser', body: 'return false;' }
  ]
};

const patch = {
  targetName: 'getUser',
  replacement: {
    body: 'return db.users.find(id);',
    params: ['id']
  }
};

const res1 = patcher.applyPatch(initialTree, patch);
assert.strictEqual(res1.success, true);
assert.strictEqual(res1.targetName, 'getUser');
assert.strictEqual(initialTree.children[0].body, 'return db.users.find(id);');
assert.strictEqual(initialTree.children[0].params[0], 'id');
console.log('✓ Test 1 Passed: AST node successfully patched in-place');

// Test 2: Target node not found returns clean error
const badPatch = { targetName: 'nonExistentFunction', replacement: {} };
const res2 = patcher.applyPatch(initialTree, badPatch);
assert.strictEqual(res2.success, false);
assert.ok(res2.error.includes('not found in tree'));
console.log('✓ Test 2 Passed: Non-existent patch target gracefully rejected');

// Test 3: Invalid patch parameters
const nullPatch = patcher.applyPatch(initialTree, null);
assert.strictEqual(nullPatch.success, false);
console.log('✓ Test 3 Passed: Null patch safely rejected');

// Test 4: Deeply nested node patching
const nestedTree = {
  type: 'Module',
  name: 'App',
  children: [
    {
      type: 'SubModule',
      name: 'Auth',
      children: [
        { type: 'Method', name: 'verifyToken', value: 'legacy_v1' }
      ]
    }
  ]
};
const deepPatch = {
  targetName: 'verifyToken',
  replacement: { value: 'secure_ed25519_v2' }
};
const res4 = patcher.applyPatch(nestedTree, deepPatch);
assert.strictEqual(res4.success, true);
assert.strictEqual(nestedTree.children[0].children[0].value, 'secure_ed25519_v2');
console.log('✓ Test 4 Passed: Deeply nested tree nodes successfully patched');

console.log('ALL 4 TESTS PASSED IN test_ast_patcher.js\n');
