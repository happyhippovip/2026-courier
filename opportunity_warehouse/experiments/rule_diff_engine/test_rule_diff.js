/**
 * test_rule_diff.js - Test suite for Semantic Rule Diff Engine
 */
const assert = require('assert');
const { RuleDiffEngine } = require('./lib/rule_diff');

console.log('--- Running test_rule_diff.js ---');

const engine = new RuleDiffEngine();

const v1 = [
  { id: 'rule_no_raw_logs', name: 'No Raw Logs', severity: 'warning', action: 'trim' },
  { id: 'rule_strip_ansi', name: 'Strip ANSI Escapes', severity: 'warning', action: 'trim' },
  { id: 'rule_error_strict', name: 'Critical Errors Only', severity: 'error', action: 'preserve' }
];

const v2 = [
  { id: 'rule_no_raw_logs', name: 'No Raw Logs Extended', severity: 'warning', action: 'trim' }, // modified
  { id: 'rule_strip_ansi', name: 'Strip ANSI Escapes', severity: 'error', action: 'drop' }, // breaking (severity + action)
  { id: 'rule_compress_ast', name: 'Compress AST Nodes', severity: 'info', action: 'compress' } // added
  // rule_error_strict is removed (breaking removal)
];

// Test 1: Basic addition and unchanged detection
const diff1 = engine.compare(v1, v1);
assert.strictEqual(diff1.summary.unchangedCount, 3, 'All 3 should be unchanged');
assert.strictEqual(diff1.summary.compatibilityScore, 100, 'Score should be 100 for identical sets');
assert.strictEqual(diff1.summary.isCompatible, true, 'Identical sets must be compatible');
console.log('✓ Test 1 Passed: Identical rule sets yield 100% compatibility score');

// Test 2: Addition and removal accurately identified
const diff2 = engine.compare(v1, v2);
assert.strictEqual(diff2.added.length, 1, 'Should detect 1 added rule');
assert.strictEqual(diff2.added[0].id, 'rule_compress_ast', 'Correct rule added');
assert.strictEqual(diff2.removed.length, 1, 'Should detect 1 removed rule');
assert.strictEqual(diff2.removed[0].id, 'rule_error_strict', 'Correct rule removed');
console.log('✓ Test 2 Passed: Accurately identifies added and removed rules');

// Test 3: Modified rules and breaking change detection
assert.strictEqual(diff2.modified.length, 2, 'Should detect 2 modified rules');
assert.ok(diff2.breakingChanges.length >= 2, 'Should identify breaking changes');
assert.strictEqual(diff2.summary.isCompatible, false, 'Sets with breaking changes must fail compatibility');
assert.ok(diff2.summary.compatibilityScore < 60, 'Score should be penalized appropriately');
console.log('✓ Test 3 Passed: Breaking changes identified with score penalty (' + diff2.summary.compatibilityScore + '/100)');

// Test 4: Markdown report generation
const mdReport = engine.generateMarkdownReport(diff2);
assert.ok(mdReport.includes('BREAKING_CHANGES_DETECTED'), 'Report must contain status badge');
assert.ok(mdReport.includes('rule_compress_ast'), 'Report must contain added rule');
assert.ok(mdReport.includes('Compatibility Score'), 'Report must contain score header');
console.log('✓ Test 4 Passed: Markdown compatibility report rendered successfully');

console.log('ALL 4 TESTS PASSED IN test_rule_diff.js\n');
