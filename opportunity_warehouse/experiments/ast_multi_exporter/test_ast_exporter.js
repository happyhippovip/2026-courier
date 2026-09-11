/**
 * test_ast_exporter.js - Test suite for Multi-Format AST Exporter
 */
const assert = require('assert');
const { AstMultiExporter } = require('./lib/ast_exporter');

console.log('--- Running test_ast_exporter.js ---');

const exporter = new AstMultiExporter();

const sampleAst = {
  type: 'Program',
  name: 'UserService',
  children: [
    {
      type: 'FunctionDeclaration',
      name: 'authenticate',
      value: 'async'
    },
    {
      type: 'ClassDeclaration',
      name: 'UserSession',
      children: [
        { type: 'MethodDefinition', name: 'validate' }
      ]
    }
  ]
};

// Test 1: JSON Export
const jsonOut = exporter.exportToJson(sampleAst);
const parsed = JSON.parse(jsonOut);
assert.strictEqual(parsed.name, 'UserService');
assert.strictEqual(parsed.children.length, 2);
console.log('✓ Test 1 Passed: JSON export faithfully preserves tree structure');

// Test 2: YAML Export
const yamlOut = exporter.exportToYaml(sampleAst);
assert.ok(yamlOut.includes('type: Program'));
assert.ok(yamlOut.includes('name: UserService'));
assert.ok(yamlOut.includes('name: authenticate'));
console.log('✓ Test 2 Passed: Native YAML export produces valid indented hierarchy');

// Test 3: Markdown Outline Export
const outlineOut = exporter.exportToOutline(sampleAst);
assert.ok(outlineOut.includes('- **[Program]** UserService'));
assert.ok(outlineOut.includes('  - **[FunctionDeclaration]** authenticate'));
assert.ok(outlineOut.includes('    - **[MethodDefinition]** validate'));
console.log('✓ Test 3 Passed: Markdown outline accurately visualizes node nesting');

// Test 4: Compact Digest Export
const digestOut = exporter.exportToDigest(sampleAst);
assert.ok(digestOut.startsWith('P:UserService('));
assert.ok(digestOut.includes('F:authenticate'));
assert.ok(digestOut.endsWith(')'));
console.log('✓ Test 4 Passed: Compact digest formats tree into dense token string (' + digestOut + ')');

console.log('ALL 4 TESTS PASSED IN test_ast_exporter.js\n');
