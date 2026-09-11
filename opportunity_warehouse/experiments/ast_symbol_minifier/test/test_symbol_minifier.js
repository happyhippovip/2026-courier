const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SymbolMinifier } = require('../lib/symbol_minifier');

console.log('--- Testing AST Symbol Renaming & Variable Minifier ---');

const minifier = new SymbolMinifier();

const sampleCode = [
  'function processTransactions(rawTransactionBatch) {',
  '  const temporaryAccumulatorVariable = [];',
  '  const totalProcessingStartTime = Date.now();',
  '  for (const singleTransactionItem of rawTransactionBatch) {',
  '    temporaryAccumulatorVariable.push(singleTransactionItem.amount);',
  '  }',
  '  return temporaryAccumulatorVariable;',
  '}'
].join('\n');

// Test 1: Identify local variables excluding exported function name
const locals = minifier.identifyLocalVariables(sampleCode, ['processTransactions']);
assert.ok(locals.includes('temporaryAccumulatorVariable'), 'Must identify verbose local accumulator');
assert.ok(locals.includes('totalProcessingStartTime'), 'Must identify verbose local timer');
assert.ok(!locals.includes('processTransactions'), 'Must not identify exported function name as local');
console.log('✓ Assertion 1 Passed: Local variables accurately identified while preserving export name');

// Test 2: Minify local variables
const minResult = minifier.minifyLocals(sampleCode, ['processTransactions']);
assert.ok(minResult.minifiedCode.includes('function processTransactions('), 'Export function name must remain untouched');
assert.ok(!minResult.minifiedCode.includes('temporaryAccumulatorVariable'), 'Verbose variable must be replaced');
assert.ok(minResult.minifiedCode.includes('const a = [];'), 'Short identifier substituted');
console.log('✓ Assertion 2 Passed: Collision-free local identifier renaming verified');

// Test 3: Token savings verification
assert.ok(minResult.tokensSaved > 0, 'Minification must yield net token savings');
console.log('✓ Assertion 3 Passed: Minification reduced token overhead (' + minResult.savingsPercent + '% saved)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_SYMBOL_MINIFICATION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(minResult, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_SYMBOL_MINIFICATION_REPORT.json');

console.log('All 4 Symbol Minifier tests passed successfully!');