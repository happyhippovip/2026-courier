const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { DeadCodeEliminator } = require('../lib/dead_code_eliminator');

console.log('--- Testing AST Call Graph & Dead Code Eliminator ---');

const eliminator = new DeadCodeEliminator();

const sampleModule = [
  'function formatOutput(data) {',
  '  return internalSanitize(data);',
  '}',
  '',
  'function internalSanitize(val) {',
  '  return String(val).trim();',
  '}',
  '',
  'function unusedLegacyAlgorithm(x, y) {',
  '  const temp = x * y;',
  '  return temp + 42;',
  '}',
  '',
  'function obsoleteCsvParser(file) {',
  '  return file.split(",");',
  '}'
].join('\n');

// Test 1: Function extraction
const fns = eliminator.extractFunctions(sampleModule);
assert.strictEqual(fns.size, 4, 'Must find exactly 4 functions');
assert.ok(fns.has('formatOutput'), 'Must identify formatOutput');
assert.ok(fns.has('internalSanitize'), 'Must identify internalSanitize');
console.log('✓ Assertion 1 Passed: Symbol declarations accurately extracted');

// Test 2: Call graph dependency resolution
const graph = eliminator.buildCallGraph(fns);
assert.ok(graph.get('formatOutput').has('internalSanitize'), 'formatOutput must call internalSanitize');
assert.strictEqual(graph.get('unusedLegacyAlgorithm').size, 0, 'unusedLegacyAlgorithm has zero dependencies');
console.log('✓ Assertion 2 Passed: Call graph correctly mapped transitive dependencies');

// Test 3: Pruning unused symbols with closure preservation
const result = eliminator.pruneDeadFunctions(sampleModule, ['formatOutput']);
assert.ok(result.prunedFunctions.includes('unusedLegacyAlgorithm'), 'unusedLegacyAlgorithm must be pruned');
assert.ok(result.prunedFunctions.includes('obsoleteCsvParser'), 'obsoleteCsvParser must be pruned');
assert.ok(!result.prunedFunctions.includes('internalSanitize'), 'internalSanitize must be preserved (called by root)');
assert.ok(result.pruneRatioPercent > 35, 'Pruning ratio must exceed 35%');
console.log('✓ Assertion 3 Passed: Dead code stripped while preserving reachable closure (' + result.pruneRatioPercent + '% saved)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_DEAD_CODE_ELIMINATION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(result, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_DEAD_CODE_ELIMINATION_REPORT.json');

console.log('All 4 Dead Code Eliminator tests passed successfully!');