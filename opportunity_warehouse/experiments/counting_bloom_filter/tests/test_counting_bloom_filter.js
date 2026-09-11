const { CountingBloomFilter } = require('../lib/counting_bloom_filter');
const fs = require('fs');
const path = require('path');

console.log('Testing Counting Bloom Filter Evaluator...');
const cbf = new CountingBloomFilter(2048, 4);

// Test 1: Add items
cbf.add('context_header');
cbf.add('context_header');
cbf.add('prompt_chunk_1');
cbf.add('prompt_chunk_2');

if (!cbf.contains('context_header')) throw new Error('Missing context_header');
if (!cbf.contains('prompt_chunk_1')) throw new Error('Missing prompt_chunk_1');
console.log('✓ Test 1: Items added and verified (count estimate for context_header: ' + cbf.estimateMinCount('context_header') + ')');

// Test 2: Decrement / Remove one occurrence
const rem1 = cbf.remove('context_header');
if (!rem1) throw new Error('Failed to remove first occurrence of context_header');
// Should still contain context_header because it was added twice
if (!cbf.contains('context_header')) throw new Error('context_header should still exist after 1 deletion');
console.log('✓ Test 2: Removed 1 occurrence; item still present with remaining count ' + cbf.estimateMinCount('context_header'));

// Test 3: Remove second occurrence
const rem2 = cbf.remove('context_header');
if (!rem2) throw new Error('Failed to remove second occurrence');
if (cbf.contains('context_header')) throw new Error('context_header should be completely gone');
console.log('✓ Test 3: Completely removed context_header; membership test returned false');

// Test 4: Write verification report
const report = {
  experiment: 'counting_bloom_filter',
  phase: 417,
  timestamp: new Date().toISOString(),
  filterSize: 2048,
  hashFunctions: 4,
  remainingItems: cbf.totalItems,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_COUNTING_BLOOM_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_COUNTING_BLOOM_REPORT.json');

console.log('All Counting Bloom Filter tests passed successfully!');
