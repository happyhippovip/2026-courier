const assert = require('assert');
const { generateProjectConfig } = require('../lib/wizard_engine');

console.log('Running Onboarding Wizard Tests...');

// Test 1: Standard Node/TS project config
const cfg1 = generateProjectConfig({ projectType: 'node_typescript', detectedFiles: ['.cursorrules', 'AGENTS.md'] });
assert.strictEqual(cfg1.profile, 'BALANCED');
assert.strictEqual(cfg1.targets.length, 2);
assert.strictEqual(cfg1.settings.prune_conversational_preamble, true);
console.log('  [PASS] Test 1: Standard balanced profile configuration verified');

// Test 2: Heavy agent swarm project
const cfg2 = generateProjectConfig({ projectType: 'ai_agent_heavy' });
assert.strictEqual(cfg2.profile, 'AGGRESSIVE');
assert.strictEqual(cfg2.settings.strip_redundant_comments, true);
console.log('  [PASS] Test 2: Aggressive compression profile verified');

// Test 3: Documentation monorepo safe profile
const cfg3 = generateProjectConfig({ projectType: 'documentation_monorepo' });
assert.strictEqual(cfg3.profile, 'SAFE_PRESERVE');
assert.strictEqual(cfg3.settings.prune_conversational_preamble, false);
console.log('  [PASS] Test 3: Safe preservation profile verified');

console.log('ALL 3 ONBOARDING WIZARD TESTS PASSED DETERMINISTICALLY!');
