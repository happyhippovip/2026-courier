const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { MerkleStateDiffEngine } = require('../lib/merkle_engine');

const engine = new MerkleStateDiffEngine();

// Test 1: Deterministic root hash computation
const state1 = {
  agent_id: 'agent_symphony_01',
  role: 'autonomous_revenue_collector',
  turns_completed: 48,
  spend_limit: 0.00
};
const tree1a = engine.buildTree(state1);
const tree1b = engine.buildTree(state1);
assert.strictEqual(tree1a.rootHash, tree1b.rootHash, 'Merkle root hash must be strictly deterministic');
console.log('✓ Test 1: Deterministic Merkle root hash computation (' + tree1a.rootHash.slice(0, 16) + '...)');

// Test 2: Diff between identical trees is empty
const diffIdentical = engine.computeDiff(tree1a, tree1b);
assert.strictEqual(diffIdentical.identical, true, 'Identical states must produce identical diff');
assert.strictEqual(diffIdentical.operationsCount, 0, 'No operations needed for identical state');
console.log('✓ Test 2: Identical trees produce empty diff');

// Test 3: Detecting add, modify, and delete operations
const state2 = {
  agent_id: 'agent_symphony_01',
  role: 'autonomous_revenue_collector',
  turns_completed: 49, // modified
  settlement_status: 'EUR5_PENDING', // added
  // spend_limit deleted
};
const tree2 = engine.buildTree(state2);
const diff = engine.computeDiff(tree1a, tree2);
assert.strictEqual(diff.identical, false, 'States must differ');
assert.strictEqual(diff.operationsCount, 3, 'Must detect 3 operations (1 add, 1 modify, 1 delete)');
assert.ok(diff.added.settlement_status, 'Should detect added field');
assert.ok(diff.modified.turns_completed, 'Should detect modified field');
assert.ok(diff.deleted.spend_limit !== undefined, 'Should detect deleted field');
console.log('✓ Test 3: Accurately detects added, modified, and deleted keys');

// Test 4: Generate patch, apply patch, and verify reconstructed target state
const patch = engine.generatePatch(state1, state2);
const applyResult = engine.applyPatch(state1, patch);
assert.strictEqual(applyResult.verified, true, 'Patch application must be cryptographically verified');
assert.strictEqual(applyResult.rootHash, tree2.rootHash, 'Reconstructed root hash must match target root hash');
assert.deepStrictEqual(applyResult.reconstructedState, state2, 'Reconstructed state must match target state exactly');

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_MERKLE_DIFF_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  diffSummary: diff,
  patchMetadata: {
    baseRootHash: patch.baseRootHash,
    targetRootHash: patch.targetRootHash,
    operationsCount: patch.operationsCount
  },
  verification: applyResult.verified
}, null, 2), 'utf8');
console.log('✓ Test 4: Merkle patch generation, application, and verification confirmed');

console.log('All Merkle State Diff Engine tests passed successfully!');
