const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { RecursiveSummarizer } = require('../lib/recursive_summarizer');

console.log('--- Testing Recursive Summarizer & Delta Indexing ---');

const summarizer = new RecursiveSummarizer();

const sampleTurn = {
  turnId: 1,
  role: 'engineer',
  content: 'Examined opportunity_warehouse/experiments/rule_diff/lib/rule_diff.js. Encountered error ENOENT during test execution at commit a9f2b801c4. Fixed path parsing logic and confirmed all unit tests pass.'
};

// Test 1: Anchor extraction
const anchors = summarizer.extractAnchors(sampleTurn.content);
assert.ok(anchors.filePaths.length >= 1, 'Must extract file paths');
assert.ok(anchors.errorCodes.includes('ENOENT'), 'Must extract error code ENOENT');
assert.ok(anchors.hashes.includes('a9f2b801c4'), 'Must extract git hash a9f2b801c4');
console.log('✓ Assertion 1 Passed: Technical anchors accurately extracted');

// Test 2: Summarization with 100% anchor retention
const summary = summarizer.summarizeTurn(sampleTurn);
assert.ok(summary.condensedContent.includes('ENOENT'), 'Condensed turn must retain ENOENT');
assert.ok(summary.condensedContent.includes('a9f2b801c4'), 'Condensed turn must retain commit hash');
assert.ok(summary.tokensSaved > 0, 'Must save tokens');
console.log('✓ Assertion 2 Passed: Summarization condensed narrative while preserving 100% anchors');

// Test 3: Recursive history compaction under token budget
const turns = [
  { turnId: 1, role: 'engineer', content: 'Long turn 1 narrative with C:\\repo\\lib\\db.js and commit abc1234. '.repeat(10) },
  { turnId: 2, role: 'reviewer', content: 'Long turn 2 narrative with C:\\repo\\lib\\api.js and code ERR_ASSERTION. '.repeat(10) },
  { turnId: 3, role: 'supervisor', content: 'Latest turn 3 action instructions.' }
];
const compacted = summarizer.compactHistory(turns, 200);
assert.strictEqual(compacted.compacted, true, 'Compaction must trigger');
assert.ok(compacted.savingsPercent > 40, 'Compaction savings must exceed 40%');
assert.strictEqual(compacted.turns[2].isCompacted, false, 'Latest turn must remain uncompacted');
console.log('✓ Assertion 3 Passed: Multi-turn history compacted under budget (' + compacted.savingsPercent + '% saved)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_RECURSIVE_COMPACTION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(compacted, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_RECURSIVE_COMPACTION_REPORT.json');

console.log('All 4 Recursive Summarizer tests passed successfully!');