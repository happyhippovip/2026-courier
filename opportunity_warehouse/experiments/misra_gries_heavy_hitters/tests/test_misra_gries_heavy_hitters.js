const { MisraGriesHeavyHitters } = require('../lib/misra_gries_heavy_hitters');
const fs = require('fs');
const path = require('path');

console.log('Testing Misra-Gries Heavy Hitters Evaluator...');
// k = 5, capacity = 4, threshold = N / 5 = 20%
const mg = new MisraGriesHeavyHitters(5);

// Generate token stream: total 1000 tokens
// Token 'symphony': 400 occurrences (40%)
// Token 'autonomous': 250 occurrences (25%)
// Token 'agent': 150 occurrences (15%)
// 200 random noise tokens (1 occurrence each)
const stream = [];
for (let i = 0; i < 400; i++) stream.push('symphony');
for (let i = 0; i < 250; i++) stream.push('autonomous');
for (let i = 0; i < 150; i++) stream.push('agent');
for (let i = 0; i < 200; i++) stream.push('noise_' + i);

// Shuffle deterministically
stream.sort((a, b) => (a.charCodeAt(0) * 31 + a.length) - (b.charCodeAt(0) * 31 + b.length));

mg.processStream(stream);

// Test 1: Heavy hitters with frequency > N/k (200 tokens) must be retained
const heavyHitters = mg.getHeavyHitters();
const foundTokens = heavyHitters.map(h => h.token);

if (!foundTokens.includes('symphony')) throw new Error('Missing heavy hitter "symphony"');
if (!foundTokens.includes('autonomous')) throw new Error('Missing heavy hitter "autonomous"');
console.log('✓ Test 1: Retained all true heavy hitters exceeding N/k threshold (40% and 25%)');

// Test 2: Bounded estimation error: f_x - N/k <= est <= f_x
// For 'symphony': actual 400, N/k = 200. est must be in [200, 400]
const estSymphony = mg.getEstimatedCount('symphony');
if (estSymphony < 200 || estSymphony > 400) {
  throw new Error('Estimated count for symphony out of bounds: ' + estSymphony);
}

// For 'autonomous': actual 250. est must be in [50, 250]
const estAuto = mg.getEstimatedCount('autonomous');
if (estAuto < 50 || estAuto > 250) {
  throw new Error('Estimated count for autonomous out of bounds: ' + estAuto);
}
console.log('✓ Test 2: Verified mathematical error bounds: f_x - N/k <= est <= f_x');

// Test 3: Noise tokens did not overwhelm capacity
if (mg.counters.size > 4) {
  throw new Error('Counters exceeded capacity k-1=4: ' + mg.counters.size);
}
console.log('✓ Test 3: Memory footprint strictly bounded by k-1=4 counters');

// Test 4: Write verification report
const report = {
  experiment: 'misra_gries_heavy_hitters',
  phase: 405,
  timestamp: new Date().toISOString(),
  k: 5,
  capacity: 4,
  totalProcessedTokens: mg.totalProcessed,
  heavyHitters: heavyHitters,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_MISRA_GRIES_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_MISRA_GRIES_REPORT.json');

console.log('All Misra-Gries Heavy Hitters tests passed successfully!');
