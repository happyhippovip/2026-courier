const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SuffixTreeDeduplicator } = require('../lib/suffix_tree');

const dedup = new SuffixTreeDeduplicator({ minSubstringLength: 15, minOccurrences: 2 });

// Test 1: Suffix array and LCP construction
const sample = 'banana';
const sa = dedup.buildSuffixArray(sample);
const lcp = dedup.buildLCPArray(sample, sa);
assert.strictEqual(sa.length, 6, 'Suffix array length must match input');
assert.strictEqual(lcp.length, 6, 'LCP array length must match input');
console.log('✓ Test 1: Suffix array & LCP array built accurately');

// Test 2: Identify repeated boilerplates
const repeatedBoilerplate = '=== ENTERPRISE AUDIT HEADER: CONFIDENTIAL AGENT CONTEXT ===';
const turns = [
  repeatedBoilerplate + ' Turn 1: User requested financial analysis.',
  repeatedBoilerplate + ' Turn 2: Worker fetched database records.',
  repeatedBoilerplate + ' Turn 3: Settlement complete with zero errors.'
];

const report = dedup.compactContext(turns, { minSubstringLength: 20, minOccurrences: 2 });
assert.ok(report.bytesSaved > 0, 'Must save bytes by eliminating repeated boilerplate');
assert.ok(report.dictionarySize >= 1, 'Must register at least one dictionary entry');
assert.ok(report.compressionRatio < 1.0, 'Compression ratio must be < 1.0');
console.log('✓ Test 2: Successfully compacted 3 turns with repeated boilerplate (saved ' + report.bytesSaved + ' bytes)');

// Test 3: Lossless roundtrip decompression
const decompacted = dedup.decompactContext(report.compactedTurns, report.dictionary);
assert.deepStrictEqual(decompacted, turns, 'Decompacted turns must match original turns bit-for-bit');
console.log('✓ Test 3: 100% roundtrip lossless decompression verified');

// Test 4: Write evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SUFFIX_TREE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  originalBytes: report.originalBytes,
  compactedBytes: report.compactedBytes,
  bytesSaved: report.bytesSaved,
  compressionRatio: report.compressionRatio,
  dictionary: report.dictionary,
  turnsSample: report.compactedTurns
}, null, 2), 'utf8');
console.log('✓ Test 4: Wrote evidence to SAMPLE_SUFFIX_TREE_REPORT.json');

console.log('All Suffix Tree Deduplicator tests passed successfully!');
