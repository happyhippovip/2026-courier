const assert = require('assert');
const { LicenseRecoveryCompiler } = require('../lib/license_recovery_compiler');

console.log('Testing LicenseRecoveryCompiler...');

const compiler = new LicenseRecoveryCompiler();

// Test 1: Compile HTML output
const html = compiler.compilePortalHtml();
assert.ok(html.startsWith('<!DOCTYPE html>'));
assert.ok(html.includes('License Recovery Portal'));
assert.ok(html.includes('orderInput'));

// Test 2: Contains recovery logic
assert.ok(html.includes('recoverLicense()'));
assert.ok(html.includes('ACT-EUR5-'));

// Test 3: Standalone self-contained structure
assert.ok(html.includes('</script>'));
assert.ok(html.includes('</html>'));

console.log('All LicenseRecoveryCompiler tests passed (3/3)!');
