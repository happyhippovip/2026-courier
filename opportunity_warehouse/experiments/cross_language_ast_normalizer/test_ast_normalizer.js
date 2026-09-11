/**
 * test_ast_normalizer.js - Test suite for Cross-Language AST Normalizer
 */
const assert = require('assert');
const { CrossLanguageAstNormalizer } = require('./lib/ast_normalizer');

console.log('--- Running test_ast_normalizer.js ---');

const normalizer = new CrossLanguageAstNormalizer();

// Test 1: Extract code blocks across multiple languages
const sampleMd = [
  '# Context Documentation',
  'Here is a JS utility:',
  '```javascript',
  '// Utility function for calculating sums',
  'function sum(a, b) {',
  '  /* return sum */',
  '  return a + b;',
  '}',
  '```',
  'And here is a Python snippet:',
  '```python',
  '# Python calculation',
  'def multiply(x, y):',
  '    return x * y',
  '```'
].join('\n');

const res1 = normalizer.normalizePrompt(sampleMd);
assert.strictEqual(res1.codeBlocksFound, 2, 'Should find 2 code blocks');
assert.ok(res1.languagesDetected.includes('javascript'));
assert.ok(res1.languagesDetected.includes('python'));
assert.ok(res1.tokensSaved > 0, 'Must save tokens by stripping comments and empty lines');
console.log('✓ Test 1 Passed: Multi-language code block extraction and token reduction verified');

// Test 2: Comment stripping precision
const jsOnly = '// Header comment\nfunction test() {\n  return 42;\n}';
const cleanedJs = normalizer.normalizeSnippet(jsOnly, 'javascript');
assert.ok(!cleanedJs.includes('// Header comment'), 'Must strip JS single-line comments');
assert.ok(cleanedJs.includes('function test()'));
console.log('✓ Test 2 Passed: JS comment stripping operates cleanly');

// Test 3: Python comment stripping
const pyOnly = '# Python header\nx = 10\n# another comment';
const cleanedPy = normalizer.normalizeSnippet(pyOnly, 'python');
assert.ok(!cleanedPy.includes('# Python header'));
assert.strictEqual(cleanedPy.trim(), 'x = 10');
console.log('✓ Test 3 Passed: Python hash comments stripped properly');

// Test 4: Pure markdown with no code blocks
const textOnly = 'Just a standard prompt without code fences.';
const res4 = normalizer.normalizePrompt(textOnly);
assert.strictEqual(res4.codeBlocksFound, 0);
assert.strictEqual(res4.tokensSaved, 0);
assert.strictEqual(res4.normalizedContent, textOnly);
console.log('✓ Test 4 Passed: Code-free markdown passes through untouched');

console.log('ALL 4 TESTS PASSED IN test_ast_normalizer.js\n');
