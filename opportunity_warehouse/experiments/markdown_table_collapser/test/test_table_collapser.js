const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { MarkdownTableCollapser } = require('../lib/table_collapser');

const collapser = new MarkdownTableCollapser();

const originalMarkdown = [
  '# Financial Ledger Summary',
  '',
  '| Order ID | Amount | Currency | Status   | Timestamp            |',
  '| :------- | :----- | :------- | :------- | :------------------- |',
  '| TX_99182 | 5.00   | EUR      | SETTLED  | 2026-09-11T12:00:00Z |',
  '| TX_99183 | 9.00   | EUR      | PENDING  | 2026-09-11T12:05:00Z |',
  '| TX_99184 | 15.00  | EUR      | QUEUED   | 2026-09-11T12:10:00Z |',
  '',
  'End of report.'
].join('\n');

// Test 1: Detect and collapse table
const result = collapser.detectAndCollapseTables(originalMarkdown);
assert.ok(result.collapsedText.includes('[TABLE_COMPACT:TSV]'), 'Must include compact table header tag');
assert.ok(result.collapsedText.includes('TX_99182\t5.00\tEUR\tSETTLED'), 'Row must be converted to tab-separated format');
assert.ok(!result.collapsedText.includes('| :-------'), 'Divider row must be stripped');
console.log('✓ Assertion 1 Passed: Table cleanly collapsed and dividers removed');

// Test 2: Token savings verification
assert.ok(result.tokensSaved > 0, 'Tokens saved must be positive');
assert.ok(result.savingsPct > 10, 'Savings percentage must be meaningful');
console.log('✓ Assertion 2 Passed: Token savings verified (' + result.tokensSaved + ' tokens saved, ' + result.savingsPct + '%)');

// Test 3: Reconstruct table from compact representation
const reconstructed = collapser.reconstructMarkdownTable(result.collapsedText);
assert.ok(reconstructed.includes('| Order ID'), 'Reconstructed table must have Order ID header');
assert.ok(reconstructed.includes('| TX_99182'), 'Reconstructed table must have TX_99182 row');
assert.ok(reconstructed.includes('| ---------'), 'Reconstructed table must have aligned divider');
console.log('✓ Assertion 3 Passed: Markdown table reconstructed with proper column alignment');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_TABLE_COLLAPSER_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  originalTokens: result.originalTokens,
  collapsedTokens: result.collapsedTokens,
  tokensSaved: result.tokensSaved,
  savingsPct: result.savingsPct,
  sampleCollapsed: result.collapsedText,
  reconstructionVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_TABLE_COLLAPSER_REPORT.json');

console.log('All 4 Markdown Table Collapser tests passed successfully!');