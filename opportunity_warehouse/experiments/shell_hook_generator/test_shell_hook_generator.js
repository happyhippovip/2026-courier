/**
 * test_shell_hook_generator.js - Test suite for Shell Hook Generator
 */
const assert = require('assert');
const { ShellHookGenerator } = require('./lib/shell_hook_generator');

console.log('--- Running test_shell_hook_generator.js ---');

const gen = new ShellHookGenerator({ targetTools: ['claude', 'aider'] });

// Test 1: Generate valid bash/zsh hooks
const bashScript = gen.generateBashZshHooks();
assert.ok(bashScript.includes('trim_context()'), 'Must define trim_context function');
assert.ok(bashScript.includes('claude() {'), 'Must generate wrapper for claude');
assert.ok(bashScript.includes('aider() {'), 'Must generate wrapper for aider');
assert.ok(bashScript.includes('command claude "$@"'), 'Must pass args to underlying command');
console.log('✓ Test 1 Passed: Bash/Zsh shell functions and wrappers generated cleanly');

// Test 2: Generate valid fish shell hooks
const fishScript = gen.generateFishHooks();
assert.ok(fishScript.includes('function trim_context'), 'Must define fish trim_context');
assert.ok(fishScript.includes('function claude --wraps claude'), 'Must define fish wrapper function');
assert.ok(fishScript.includes('command claude $argv'), 'Must use fish argv syntax');
console.log('✓ Test 2 Passed: Fish shell function definitions adhere to syntax rules');

// Test 3: Custom tool wrapper configuration
const customGen = new ShellHookGenerator({ targetTools: ['cline', 'windsurf'] });
const customBash = customGen.generateBashZshHooks();
assert.ok(customBash.includes('cline() {'), 'Must include custom tool cline');
assert.ok(customBash.includes('windsurf() {'), 'Must include custom tool windsurf');
assert.ok(!customBash.includes('claude() {'), 'Must not include unrequested tools');
console.log('✓ Test 3 Passed: Custom tool configurations properly scoped');

// Test 4: Install snippet packaging
const snippet = gen.generateInstallSnippet('bash');
assert.strictEqual(snippet.shellType, 'bash');
assert.ok(snippet.instructions.includes('Append the content'));
console.log('✓ Test 4 Passed: Install snippet packaged with clear setup instructions');

console.log('ALL 4 TESTS PASSED IN test_shell_hook_generator.js\n');
