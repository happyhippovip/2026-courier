const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CompressedSuffixArrayEvaluator } = require('../lib/compressed_suffix_array_evaluator');

console.log('Testing Compressed Suffix Array Evaluator...');

const evaluator = new CompressedSuffixArrayEvaluator();
const stream = ['tok_a', 'tok_b', 'tok_c', 'tok_a', 'tok_b', 'tok_d', 'tok_a', 'tok_b'];
evaluator.build(stream);

// Test 1: Pattern Count
const cnt = evaluator.count(['tok_a', 'tok_b']);
assert.strictEqual(cnt, 3, 'Pattern tok_a, tok_b should appear exactly 3 times');
console.log('✓ Test 1: Exact pattern count verified via BWT backward search (count: 3)');

// Test 2: Locate Pattern Indices
const locs = evaluator.locate(['tok_a', 'tok_b']);
assert.deepStrictEqual(locs, [0, 3, 6], 'Pattern indices must match [0, 3, 6]');
console.log('✓ Test 2: Substring locate queries accurately returned starting positions [0, 3, 6]');

// Test 3: Missing Pattern
const missingCount = evaluator.count(['tok_non_existent']);
assert.strictEqual(missingCount, 0);
assert.deepStrictEqual(evaluator.locate(['tok_non_existent']), []);
console.log('✓ Test 3: Missing query gracefully returns 0 count and empty locations');

// Test 4: Evidence Report Export
const evidenceReport = {
  experiment: 'compressed_suffix_array_evaluator',
  timestamp: new Date().toISOString(),
  tokenCount: stream.length,
  compressionRatio: evaluator.getCompressionRatio(),
  queries: [
    { pattern: ['tok_a', 'tok_b'], count: cnt, locations: locs },
    { pattern: ['tok_non_existent'], count: missingCount }
  ],
  status: 'VERIFIED'
};

const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_COMPRESSED_SUFFIX_ARRAY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(evidenceReport, null, 2), 'utf8');
assert.strictEqual(fs.existsSync(evidencePath), true);
console.log('✓ Test 4: Evidence report written to SAMPLE_COMPRESSED_SUFFIX_ARRAY_REPORT.json');

console.log('All Compressed Suffix Array Evaluator tests passed successfully!');
