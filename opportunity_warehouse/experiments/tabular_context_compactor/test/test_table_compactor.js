const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TabularContextCompactor } = require('../lib/table_compactor');

console.log('--- Testing Semantic Markdown Table Compactor ---');

const compactor = new TabularContextCompactor();

const sampleTable = [
  '| Metric Name           | Value       | Status   | Notes                |',
  '| :-------------------- | :---------- | :------- | :------------------- |',
  '| Latency TTFT          | 450ms       | OK       | Nominal gateway ping |',
  '| Memory Allocation     | 128MB       | OK       | In-memory heap       |',
  '| Token Compaction      | 68.4%       | OK       | AST dead code prune  |'
].join('\n');

// Test 1: Table parsing
const parsed = compactor.parseTable(sampleTable);
assert.ok(parsed !== null, 'Table must parse successfully');
assert.strictEqual(parsed.headers.length, 4, 'Must parse 4 columns');
assert.strictEqual(parsed.dataRows.length, 3, 'Must parse 3 data rows');
console.log('✓ Assertion 1 Passed: Table parsed into structured headers and rows');

// Test 2: Whitespace padding stripping
const stripped = compactor.stripPadding(sampleTable);
assert.ok(!stripped.includes('           '), 'Padded whitespace must be stripped');
assert.ok(stripped.includes('|Metric Name|Value|Status|Notes|'), 'Headers must be unpadded');
console.log('✓ Assertion 2 Passed: Padded whitespace stripped without corruption');

// Test 3: Redundant uniform column elimination
const compacted = compactor.compactTable(sampleTable);
assert.strictEqual(compacted.columnsDropped, 1, 'Status column (all OK) must be dropped');
assert.strictEqual(compacted.columnsRetained, 3, '3 meaningful columns retained');
assert.ok(compacted.savingsPercent > 40, 'Compacted table must achieve >40% token savings');
console.log('✓ Assertion 3 Passed: Redundant uniform column dropped (' + compacted.savingsPercent + '% saved)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_TABULAR_COMPACTION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(compacted, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_TABULAR_COMPACTION_REPORT.json');

console.log('All 4 Tabular Compactor tests passed successfully!');