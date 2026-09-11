const assert = require('assert');
const { generateBashInstaller, generatePowerShellInstaller } = require('../lib/installer_generator');

console.log('Running One-Line Installer Generator Tests...');

// Test 1: Bash installer generation
const bashScript = generateBashInstaller({ packageName: 'agent-context-trimmer', version: '1.0.0' });
assert.ok(bashScript.includes('#!/usr/bin/env bash'), 'Bash script must contain shebang');
assert.ok(bashScript.includes('agent-context-trimmer'), 'Must contain package name');
assert.ok(bashScript.includes('command -v node'), 'Must check Node.js requirement');
console.log('  [PASS] Test 1: Bash installer script generation validated');

// Test 2: PowerShell installer generation
const psScript = generatePowerShellInstaller({ packageName: 'agent-context-trimmer', version: '1.0.0' });
assert.ok(psScript.includes("$ErrorActionPreference = 'Stop'"), 'PowerShell script must set strict error handling');
assert.ok(psScript.includes('Expand-Archive'), 'Must support built-in PowerShell unzipping');
assert.ok(psScript.includes('Get-Command node'), 'Must verify Node.js runtime');
console.log('  [PASS] Test 2: PowerShell installer script generation validated');

// Test 3: Custom options support
const customBash = generateBashInstaller({ packageName: 'custom-tool', version: '2.5.0', installDir: '/opt/custom' });
assert.ok(customBash.includes('custom-tool v2.5.0'), 'Custom options must be reflected');
assert.ok(customBash.includes('/opt/custom'), 'Custom install dir must be reflected');
console.log('  [PASS] Test 3: Custom parameterization validated');

console.log('ALL 3 ONE-LINE INSTALLER TESTS PASSED DETERMINISTICALLY!');
