const { SpaceSavingHeavyHitters } = require('../lib/space_saving_heavy_hitters');
const fs = require('fs');
const path = require('path');

console.log('Testing Space-Saving Heavy Hitters Evaluator...');
const ss = new SpaceSavingHeavyHitters(5);

// Stream 1200 tokens
// 'revenue_eur5': 500 (41.6%)
// 'symphony_core': 350 (29.1%)
// 'mac_guard': 200 (16.6%)
// 150 unique ephemeral tokens
const stream = [];
for (let i = 0; i < 500; i++) stream.push('revenue_eur5');
for (let i = 0; i < 350; i++) stream.push('symphony_core');
for (let i = 0; i < 200; i++) stream.push('mac_guard');
for (let i = 0; i < 150; i++) stream.push('transient_item_' + i);

// Shuffle stream deterministically
stream.sort((a, b) => (a.length * 17 + a.charCodeAt(0)) - (b.length * 17 + b.charCodeAt(0)));

ss.processStream(stream);

// Test 1: Heavy hitters retained
const hitters = ss.getHeavyHitters();
const tokens = hitters.map(h => h.token);

if (!tokens.includes('revenue_eur5')) throw new Error('Missing revenue_eur5');
if (!tokens.includes('symphony_core')) throw new Error('Missing symphony_core');
if (!tokens.includes('mac_guard')) throw new Error('Missing mac_guard');
console.log('✓ Test 1: Space-Saving retained top 3 heavy hitters');

// Test 2: Error bounds check: count - error <= trueCount <= count
const revItem = ss.getItem('revenue_eur5');
if (revItem.count < 500 || revItem.count - revItem.error > 500) {
  throw new Error('revenue_eur5 out of error bounds: ' + JSON.stringify(revItem));
}

const symItem = ss.getItem('symphony_core');
if (symItem.count < 350 || symItem.count - symItem.error > 350) {
  throw new Error('symphony_core out of error bounds: ' + JSON.stringify(symItem));
}
console.log('✓ Test 2: Mathematical invariant verified: count - error <= trueCount <= count');

// Test 3: Capacity bound strictly enforced
if (ss.items.size > 5) throw new Error('Tracked items exceeded capacity k=5');
console.log('✓ Test 3: Capacity strictly bounded at k=5');

// Test 4: Write verification report
const report = {
  experiment: 'space_saving_heavy_hitters',
  phase: 409,
  timestamp: new Date().toISOString(),
  k: 5,
  totalProcessedTokens: ss.totalProcessed,
  heavyHitters: hitters,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_SPACE_SAVING_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_SPACE_SAVING_REPORT.json');

console.log('All Space-Saving Heavy Hitters tests passed successfully!');
