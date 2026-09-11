const { QuotientFilter } = require('../lib/quotient_filter');
const fs = require('fs');
const path = require('path');

console.log('Testing Quotient Filter Evaluator...');
// 2^8 = 256 slots, 8-bit remainder
const qf = new QuotientFilter(8, 8);

// Test 1: Insertion and Lookup
const items = ['token_system_rule', 'token_user_input', 'token_rag_document', 'token_tool_result'];
items.forEach(it => qf.insert(it));

if (qf.size !== 4) throw new Error('Expected size 4, got ' + qf.size);
for (const it of items) {
  if (!qf.contains(it)) throw new Error('Item missing from filter: ' + it);
}
console.log('✓ Test 1: Inserted and verified 4 distinct context tokens');

// Test 2: Negative membership
if (qf.contains('unseen_alien_token_xyz')) {
  throw new Error('False positive on non-existent token');
}
console.log('✓ Test 2: Correctly returned false for non-existent token');

// Test 3: Idempotent duplicate insertions
qf.insert('token_system_rule');
if (qf.size !== 4) throw new Error('Duplicate insertion increased size');
console.log('✓ Test 3: Duplicate insertion ignored idempotently');

// Test 4: Write verification report
const report = {
  experiment: 'quotient_filter',
  phase: 421,
  timestamp: new Date().toISOString(),
  qBits: 8,
  rBits: 8,
  totalSlots: qf.numSlots,
  loadedItems: qf.size,
  loadFactor: qf.size / qf.numSlots,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_QUOTIENT_FILTER_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_QUOTIENT_FILTER_REPORT.json');

console.log('All Quotient Filter tests passed successfully!');
