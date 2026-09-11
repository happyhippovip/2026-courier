const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { LevenshteinDeltaPatcher } = require('../lib/delta_patcher');

const patcher = new LevenshteinDeltaPatcher();

const originalSourceCode = [
  'function processPayment(orderId, amount) {',
  '  console.log("Processing order: " + orderId);',
  '  if (amount <= 0) throw new Error("Invalid amount");',
  '  const status = "PENDING";',
  '  return { orderId, amount, status };',
  '}'
].join('\n');

const updatedSourceCode = [
  'function processPayment(orderId, amount) {',
  '  console.log("Processing order: " + orderId);',
  '  if (amount <= 0) throw new Error("Invalid amount");',
  '  const status = "SETTLED_EUR5"; // updated to verified settlement',
  '  const settledAt = 1789128000; // added settlement timestamp',
  '  return { orderId, amount, status, settledAt };',
  '}'
].join('\n');

// Test 1: Compute diff hunks
const hunks = patcher.computeLineDiff(originalSourceCode, updatedSourceCode);
assert.strictEqual(hunks.length, 1, 'Should produce exactly 1 localized diff hunk');
assert.strictEqual(hunks[0].removed.length, 3, 'Should remove 3 old lines');
assert.strictEqual(hunks[0].added.length, 4, 'Should insert 4 updated lines');
console.log('✓ Assertion 1 Passed: Localized diff hunk accurately identified');

// Test 2: Apply patch and verify 100% byte fidelity reconstruction
const reconstructed = patcher.applyPatch(originalSourceCode, hunks);
assert.strictEqual(reconstructed, updatedSourceCode, 'Reconstructed source code must match updated code exactly');
console.log('✓ Assertion 2 Passed: Patch applied with 100% byte fidelity');

// Test 3: Calculate patch token efficiency
const efficiency = patcher.calculatePatchEfficiency(originalSourceCode, updatedSourceCode, hunks);
assert.ok(efficiency.patchTokens > 0, 'Patch tokens must be positive');
assert.strictEqual(efficiency.hunkCount, 1);
console.log('✓ Assertion 3 Passed: Patch efficiency verified (' + efficiency.patchTokens + ' patch tokens vs ' + efficiency.fullFileTokens + ' full file tokens)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_LEVENSHTEIN_DIFF_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  hunksCount: hunks.length,
  sampleHunk: hunks[0],
  efficiency,
  reconstructionVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_LEVENSHTEIN_DIFF_REPORT.json');

console.log('All 4 Levenshtein Delta Patcher tests passed successfully!');