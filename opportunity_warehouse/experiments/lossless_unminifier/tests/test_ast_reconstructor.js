const assert = require('assert');
const { AstReconstructor } = require('../lib/ast_reconstructor');

console.log('Testing AstReconstructor...');

const recon = new AstReconstructor();

// Test 1: Parse to AST
const prompt = '# System Directives\n- MUST respond in JSON\n- ALWAYS preserve schema\n```json\n{"key":"val"}\n```';
const ast = recon.parseToAst(prompt);
assert.strictEqual(ast.type, 'Root');
assert.strictEqual(ast.children.length, 4);
assert.strictEqual(ast.children[0].type, 'Header');
assert.strictEqual(ast.children[3].type, 'CodeBlock');

// Test 2: Reconstruct markdown
const reconstructed = recon.reconstructMarkdown(ast);
assert.ok(reconstructed.includes('# System Directives'));
assert.ok(reconstructed.includes('MUST respond in JSON'));
assert.ok(reconstructed.includes('{"key":"val"}'));

// Test 3: Verify lossless directives
const check = recon.verifyLosslessDirectives(prompt, reconstructed);
assert.strictEqual(check.lossless, true);
assert.strictEqual(check.missingDirectives.length, 0);

// Test 4: Empty input
const emptyAst = recon.parseToAst('');
assert.strictEqual(emptyAst.children.length, 0);
assert.strictEqual(recon.reconstructMarkdown(emptyAst), '');

console.log('All AstReconstructor tests passed (4/4)!');
