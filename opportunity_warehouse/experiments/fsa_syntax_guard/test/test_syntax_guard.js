const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { FsaSyntaxGuard } = require('../lib/syntax_guard');

const guard = new FsaSyntaxGuard();

// Test 1: Complete JSON passes with clean terminal state
const validJson = '{"orderId": "TX_99182", "amount": 5.00, "items": ["pkg_v1"]}';
const validRes = guard.inspectStream(validJson);
assert.strictEqual(validRes.isCleanTerminal, true, 'Valid JSON must be clean terminal');
assert.strictEqual(validRes.isTruncated, false);
console.log('✓ Assertion 1 Passed: Valid completed JSON verified with clean terminal state');

// Test 2: Abruptly cut-off JSON detected accurately
const truncated1 = '{"orderId": "TX_99182", "amount": 5.00, "items": ["pkg_v1'; // cut off inside array string
const truncRes1 = guard.inspectStream(truncated1);
assert.strictEqual(truncRes1.isTruncated, true, 'Truncation must be detected');
assert.strictEqual(truncRes1.inString, true, 'Must detect inside string state');
console.log('✓ Assertion 2 Passed: Truncation inside string detected correctly');

// Test 3: Auto-repair produces valid, parseable JSON
const repaired1 = guard.repairTruncatedJson(truncated1);
assert.doesNotThrow(() => JSON.parse(repaired1), 'Repaired text must be valid JSON parseable');
const parsed = JSON.parse(repaired1);
assert.strictEqual(parsed.orderId, 'TX_99182');
assert.strictEqual(parsed.amount, 5.00);
assert.strictEqual(parsed.items[0], 'pkg_v1');
console.log('✓ Assertion 3 Passed: Truncated JSON successfully auto-repaired and parsed without errors');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_FSA_SYNTAX_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  truncatedSample: truncated1,
  repairedOutput: repaired1,
  parsedPayload: parsed,
  fsaComplianceVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_FSA_SYNTAX_REPORT.json');

console.log('All 4 FSA Syntax Guard tests passed successfully!');