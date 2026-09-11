const assert = require('assert');
const { extractCodeBlocks, checkDelimiterBalance, validateMarkdownCodeBlocks } = require('../lib/syntax_guard');

console.log('Running AST Syntax Guard Tests...');

// Test 1: Extract code blocks
const md = 'Intro\n```typescript\nconst a = 1;\n```\nMiddle\n```json\n{"key": "val"}\n```';
const blocks = extractCodeBlocks(md);
assert.strictEqual(blocks.length, 2);
assert.strictEqual(blocks[0].language, 'typescript');
assert.strictEqual(blocks[1].language, 'json');
console.log('  [PASS] Test 1: Code block extraction verified');

// Test 2: Balanced delimiters
const balanced = checkDelimiterBalance('function test() { const arr = [1, 2, 3]; return { x: arr }; }');
assert.strictEqual(balanced.is_balanced, true);
console.log('  [PASS] Test 2: Balanced delimiters validated');

// Test 3: Unbalanced delimiter detection
const broken = checkDelimiterBalance('function bad() { return [1, 2; }');
assert.strictEqual(broken.is_balanced, false);
assert.ok(broken.error.includes("Unmatched closing delimiter '}'"));
console.log('  [PASS] Test 3: Unmatched delimiter detected');

// Test 4: Validate markdown code blocks
const mixedMd = 'Valid block:\n```js\nconst x = (1 + 2);\n```\nBroken:\n```ts\nconst y = { a: [1 };\n```';
const res = validateMarkdownCodeBlocks(mixedMd);
assert.strictEqual(res.total_blocks, 2);
assert.strictEqual(res.valid_blocks, 1);
assert.strictEqual(res.error_count, 1);
console.log('  [PASS] Test 4: Markdown code block validation verified');

console.log('ALL 4 AST SYNTAX GUARD TESTS PASSED DETERMINISTICALLY!');
