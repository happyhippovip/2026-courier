const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { PersistentBSTSetFilter } = require('./lib/persistent_bst_set_filter');

console.log('Testing Persistent BST Set Filter...');

const setFilter = new PersistentBSTSetFilter();

// Test 1: Build Set A { 10, 20, 30, 40 }
let setA = null;
[10, 20, 30, 40].forEach(k => { setA = setFilter.insert(setA, k); });
setFilter.saveSnapshot('setA', setA);
assert.strictEqual(setA.size, 4);
assert.strictEqual(setFilter.contains(setA, 20), true);
assert.strictEqual(setFilter.contains(setA, 99), false);
console.log('✓ Test 1: Set A constructed and contains queries verified');

// Test 2: Build Set B { 30, 40, 50, 60 }
let setB = null;
[30, 40, 50, 60].forEach(k => { setB = setFilter.insert(setB, k); });
setFilter.saveSnapshot('setB', setB);
assert.strictEqual(setB.size, 4);
console.log('✓ Test 2: Set B constructed');

// Test 3: Set Union -> { 10, 20, 30, 40, 50, 60 }
const unionSet = setFilter.union(setA, setB);
assert.strictEqual(unionSet.size, 6);
assert.deepStrictEqual(setFilter.toList(unionSet), [10, 20, 30, 40, 50, 60]);
console.log('✓ Test 3: Set Union verified');

// Test 4: Set Intersection -> { 30, 40 }
const interSet = setFilter.intersection(setA, setB);
assert.strictEqual(interSet.size, 2);
assert.deepStrictEqual(setFilter.toList(interSet), [30, 40]);
console.log('✓ Test 4: Set Intersection verified');

// Test 5: Set Difference (A  B) -> { 10, 20 }
const diffSet = setFilter.difference(setA, setB);
assert.strictEqual(diffSet.size, 2);
assert.deepStrictEqual(setFilter.toList(diffSet), [10, 20]);
console.log('✓ Test 5: Set Difference verified');

// Test 6: Export evidence report
const evidencePath = path.join(__dirname, '..', '..', 'evidence', 'SAMPLE_BST_SET_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  timestamp: new Date().toISOString(),
  phase: 581,
  metrics: setFilter.getMetrics(),
  unionKeys: setFilter.toList(unionSet),
  interKeys: setFilter.toList(interSet),
  diffKeys: setFilter.toList(diffSet),
  verdict: 'PERSISTENT_BST_SET_FILTER_VERIFIED_100_PERCENT'
}, null, 2), 'utf8');
console.log('✓ Test 6: Evidence report written to SAMPLE_BST_SET_REPORT.json');

console.log('All Persistent BST Set Filter tests passed successfully!');
