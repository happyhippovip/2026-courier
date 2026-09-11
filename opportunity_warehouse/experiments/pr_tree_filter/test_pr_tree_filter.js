const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { PRPoint, PriorityRTreeFilter } = require('./lib/pr_tree_filter');

console.log('Testing Priority R-Tree Filter...');

const prTree = new PriorityRTreeFilter(2); // Small capacity to force hierarchical splits

const samplePoints = [
  new PRPoint(1, 10, 'token_1'),
  new PRPoint(3, 50, 'token_3_high_saliency'),
  new PRPoint(5, 20, 'token_5'),
  new PRPoint(7, 95, 'token_7_peak_saliency'),
  new PRPoint(10, 30, 'token_10'),
  new PRPoint(12, 85, 'token_12_high_saliency'),
  new PRPoint(15, 15, 'token_15')
];

prTree.build(samplePoints);

// Test 1: Full range query returns all points
const allPts = prTree.query2DRange(0, 20, 0, 100);
assert.strictEqual(allPts.length, 7);
console.log('✓ Test 1: Full 2D bounding query returned all 7 points');

// Test 2: Orthogonal window query [2..8] in position, [40..100] in saliency
const windowResults = prTree.query2DRange(2, 8, 40, 100);
assert.strictEqual(windowResults.length, 2);
const windowTokens = windowResults.map(p => p.data).sort();
assert.deepStrictEqual(windowTokens, ['token_3_high_saliency', 'token_7_peak_saliency']);
console.log('✓ Test 2: Orthogonal window query [2..8] x [40..100] matched exact high-saliency tokens');

// Test 3: Top-K range query
const top2 = prTree.topKRange(0, 15, 0, 100, 2);
assert.strictEqual(top2.length, 2);
assert.strictEqual(top2[0].y, 95); // token_7
assert.strictEqual(top2[1].y, 85); // token_12
console.log('✓ Test 3: Top-2 highest saliency tokens extracted in descending priority order');

// Test 4: Empty range query
const emptyResults = prTree.query2DRange(100, 200, 0, 100);
assert.strictEqual(emptyResults.length, 0);
console.log('✓ Test 4: Non-intersecting bounding box returned 0 matches cleanly');

// Test 5: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_PR_TREE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 553,
  metrics: prTree.getMetrics(),
  sampleWindowResults: windowResults,
  top2,
  verdict: 'PR_TREE_FILTER_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_PR_TREE_REPORT.json');

console.log('All Priority R-Tree Filter tests passed successfully!');
