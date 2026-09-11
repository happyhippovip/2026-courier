const assert = require('assert');
const { TuiTreeVisualizer } = require('../lib/tui_tree_visualizer');

console.log('Testing TuiTreeVisualizer...');

const visualizer = new TuiTreeVisualizer();

// Test 1: Render single node
const root = { name: 'RootContext', tokens: 1000, pruned: false, children: [] };
const single = visualizer.renderTree(root);
assert.ok(single.includes('RootContext'));
assert.ok(single.includes('✔ [KEPT]'));
assert.ok(single.includes('(1000 tokens)'));

// Test 2: Render nested tree
const fullTree = {
  name: 'SystemPrompt',
  tokens: 1500,
  pruned: false,
  children: [
    { name: 'CoreDirectives', tokens: 400, pruned: false },
    {
      name: 'GuidelinePolicies',
      tokens: 800,
      pruned: false,
      children: [
        { name: 'RedundantHeader', tokens: 300, pruned: true },
        { name: 'ActiveGuidelines', tokens: 500, pruned: false }
      ]
    },
    { name: 'DecorativeAscii', tokens: 300, pruned: true }
  ]
};

const report = visualizer.generateReport(fullTree);
assert.ok(report.treeGraph.includes('CoreDirectives'));
assert.ok(report.treeGraph.includes('RedundantHeader ✂ [PRUNED]'));
assert.ok(report.treeGraph.includes('ActiveGuidelines ✔ [KEPT]'));

// Test 3: Metrics verification (1500 + 400 + 800 + 300 + 500 + 300 = 3800)
assert.strictEqual(report.metrics.totalTokens, 3800);
assert.strictEqual(report.metrics.prunedTokens, 600);
assert.strictEqual(report.metrics.keptTokens, 3200);
assert.strictEqual(report.metrics.reductionPct, 15.79);

// Test 4: Empty input
assert.strictEqual(visualizer.renderTree(null), '');

console.log('All TuiTreeVisualizer tests passed (4/4)!');
