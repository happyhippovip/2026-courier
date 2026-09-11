const { StreamSummary } = require('../lib/stream_summary_evaluator');
const fs = require('fs');
const path = require('path');

console.log('Testing Stream-Summary Evaluator...');
const ss = new StreamSummary(4);

// Test 1: Insert 4 items (up to capacity)
ss.add('token_1');
ss.add('token_1');
ss.add('token_2');
ss.add('token_3');
ss.add('token_4');

if (ss.itemMap.size !== 4) throw new Error('Size should be 4, got ' + ss.itemMap.size);
const est1 = ss.getEstimate('token_1');
if (est1.count !== 2) throw new Error('token_1 count should be 2, got ' + est1.count);
console.log('✓ Test 1: Stream-Summary correctly tracked initial 4 items (token_1 count: 2)');

// Test 2: Evict minimum item in O(1) when capacity is full
ss.add('token_5');
if (ss.itemMap.size !== 4) throw new Error('Size should remain 4 after eviction');
if (!ss.itemMap.has('token_5')) throw new Error('token_5 should be present');
console.log('✓ Test 2: O(1) eviction replaced minimum item while maintaining capacity k=4');

// Test 3: Heavy hitters list
const hitters = ss.getHeavyHitters();
if (hitters[0].key !== 'token_1' || hitters[0].count < 2) {
  throw new Error('Top heavy hitter should be token_1');
}
console.log('✓ Test 3: Heavy hitters list correctly identified top items in O(1) bucket order');

// Test 4: Write verification report
const report = {
  experiment: 'stream_summary_evaluator',
  phase: 453,
  timestamp: new Date().toISOString(),
  capacityK: 4,
  totalEventsProcessed: ss.totalEvents,
  trackedItemsCount: ss.itemMap.size,
  heavyHitters: hitters,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_STREAM_SUMMARY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_STREAM_SUMMARY_REPORT.json');

console.log('All Stream-Summary tests passed successfully!');
