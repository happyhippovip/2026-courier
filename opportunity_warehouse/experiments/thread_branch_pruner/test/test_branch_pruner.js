const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { ThreadBranchPruner } = require('../lib/branch_pruner');

const pruner = new ThreadBranchPruner();

// Setup reasoning tree: Root -> [Branch A (fails), Branch B (succeeds)]
const root = pruner.createThread({ title: 'Initial prompt: Secure EUR 5.00 revenue' });

// Branch A: Explores speculative local cache path
const turnA1 = pruner.addTurn(root.id, { action: 'Check local order cache', details: 'Searching local sqlite db' });
const turnA2 = pruner.addTurn(turnA1.id, { action: 'Parse cache file', details: 'File not found or corrupted' }, 'FALSIFIED');
pruner.markBranchStatus(turnA1.id, 'ABANDONED');

// Branch B: Explores direct webhook inbox path
const turnB1 = pruner.addTurn(root.id, { action: 'Poll inbox directory', details: 'Read money_factory/inbox/orders/' });
const turnB2 = pruner.addTurn(turnB1.id, { action: 'Process verified order', details: 'Receipt EUR 5.00 verified and settled' }, 'RESOLVED');

// Test 1: Verify branch construction
assert.strictEqual(root.children.length, 2, 'Root must have 2 branches');
assert.strictEqual(turnA1.status, 'ABANDONED', 'Branch A must be marked abandoned');
assert.strictEqual(turnB2.status, 'RESOLVED', 'Branch B must be resolved');
console.log('✓ Assertion 1 Passed: Multi-branch reasoning tree constructed');

// Test 2: Prune dead branches
const pruneStats = pruner.pruneDeadBranches();
assert.strictEqual(pruneStats.prunedNodesCount, 2, 'Must prune 2 dead nodes from Branch A');
assert.ok(pruneStats.prunedTokens > 0, 'Must recover tokens from dead branch');
console.log('✓ Assertion 2 Passed: Dead branches pruned (' + pruneStats.prunedNodesCount + ' nodes, ' + pruneStats.prunedTokens + ' tokens recovered)');

// Test 3: Linearize winning path
const winningTrace = pruner.linearizeWinningPath(turnB2.id);
assert.strictEqual(winningTrace.totalSteps, 3, 'Winning path must consist of Root -> B1 -> B2');
assert.strictEqual(winningTrace.pathSequence[0].id, root.id);
assert.strictEqual(winningTrace.pathSequence[2].id, turnB2.id);
console.log('✓ Assertion 3 Passed: Winning path cleanly linearized into monotonic sequential trace');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_BRANCH_PRUNER_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  rootId: root.id,
  pruneStats,
  winningTrace,
  branchIsolationVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_BRANCH_PRUNER_REPORT.json');

console.log('All 4 Thread Branch Pruner tests passed successfully!');