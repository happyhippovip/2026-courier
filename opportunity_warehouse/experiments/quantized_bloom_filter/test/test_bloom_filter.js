const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { QuantizedBloomFilter } = require('../lib/bloom_filter');

const filter = new QuantizedBloomFilter(1024, 3);

const insertedItems = [
  'tool_call:poll_orders:turn_1',
  'order_receipt:EUR5:tx_99182',
  'mutex_lock:0x4910',
  'user_intent:check_status',
  'safety_gate:spend_zero'
];

// Test 1: Added items return true (no false negatives)
for (const item of insertedItems) {
  filter.add(item);
}
for (const item of insertedItems) {
  assert.strictEqual(filter.has(item), true, 'Inserted item must test positive: ' + item);
}
console.log('✓ Assertion 1 Passed: All 5 inserted items tested positive with zero false negatives');

// Test 2: Non-inserted items return false with high fidelity
const nonInsertedItems = [
  'tool_call:delete_database:turn_1',
  'unauthorized_spend:EUR1000',
  'unknown_random_token_491028'
];
for (const item of nonInsertedItems) {
  assert.strictEqual(filter.has(item), false, 'Non-inserted item should test negative: ' + item);
}
console.log('✓ Assertion 2 Passed: Non-inserted items tested negative');

// Test 3: False positive probability estimation
const fpProb = filter.estimateFalsePositiveProbability();
assert.ok(fpProb < 0.01, 'FP probability should be <1% for 5 items in 1024 bits');
console.log('✓ Assertion 3 Passed: Theoretical false positive probability verified (' + (fpProb * 100).toFixed(3) + '%)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_QUANTIZED_BLOOM_REPORT.json');
const report = {
  timestamp: new Date().toISOString(),
  sizeBits: filter.sizeBits,
  totalBytes: filter.bitset.length,
  itemCount: filter.itemCount,
  falsePositiveRate: fpProb,
  sampleItems: insertedItems,
  bloomFilterVerified: true
};
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_QUANTIZED_BLOOM_REPORT.json');

console.log('All 4 Quantized Bloom Filter tests passed successfully!');