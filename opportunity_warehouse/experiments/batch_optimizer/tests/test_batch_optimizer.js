const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { auditWorkspaceBatch, findRulesFiles } = require('../lib/batch_optimizer');

console.log('Running Multi-Workspace Batch Optimizer Tests...');

// Setup temporary mock workspaces
const tmpBase = path.join(os.tmpdir(), 'test_batch_workspaces_' + Date.now());
fs.mkdirSync(tmpBase, { recursive: true });

const ws1 = path.join(tmpBase, 'service-auth');
const ws2 = path.join(tmpBase, 'service-billing');
fs.mkdirSync(ws1, { recursive: true });
fs.mkdirSync(ws2, { recursive: true });

fs.writeFileSync(path.join(ws1, '.cursorrules'), '# Auth Rules\nStrict types only.\n' + 'line\n'.repeat(50), 'utf8');
fs.writeFileSync(path.join(ws2, 'AGENTS.md'), '# Billing Rules\nPure functions only.\n' + 'rule\n'.repeat(80), 'utf8');

try {
  // Test 1: Scan multiple workspaces
  const report = auditWorkspaceBatch([ws1, ws2]);
  assert.strictEqual(report.total_workspaces_scanned, 2);
  assert.strictEqual(report.workspaces.length, 2);
  console.log('  [PASS] Test 1: Multiple workspaces scanned and audited');

  // Test 2: Rules files discovery
  assert.strictEqual(report.workspaces[0].rules_files_found, 1);
  assert.strictEqual(report.workspaces[1].rules_files_found, 1);
  console.log('  [PASS] Test 2: Rules files detected across projects');

  // Test 3: Aggregated savings calculations
  assert.ok(report.aggregate_total_tokens > 0);
  assert.ok(report.aggregate_tokens_saved > 0);
  assert.ok(report.aggregate_monthly_cost_saved_usd > 0);
  console.log('  [PASS] Test 3: Consolidated token and cost savings calculated');

  // Test 4: Empty workspace handling
  const emptyReport = auditWorkspaceBatch([]);
  assert.strictEqual(emptyReport.total_workspaces_scanned, 0);
  assert.strictEqual(emptyReport.aggregate_total_tokens, 0);
  console.log('  [PASS] Test 4: Empty input handled safely');
} finally {
  // Clean up mock dirs
  fs.rmSync(tmpBase, { recursive: true, force: true });
}

console.log('ALL 4 BATCH OPTIMIZER TESTS PASSED DETERMINISTICALLY!');
