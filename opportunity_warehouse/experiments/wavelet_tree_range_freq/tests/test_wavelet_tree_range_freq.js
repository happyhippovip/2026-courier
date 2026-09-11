const { WaveletTreeRangeFreq } = require('../lib/wavelet_tree_range_freq');
const fs = require('fs');
const path = require('path');

console.log('Testing Wavelet Tree Range Frequency Filter...');

// Token sequence: 20 tokens with known clusters of repeated tokens
const tokenSeq = [7, 42, 7, 19, 42, 42, 85, 7, 42, 99, 7, 7, 42, 19, 7, 33, 42, 7, 7, 42];
const wtrf = new WaveletTreeRangeFreq(tokenSeq, 127);

// Test 1: Exact frequency query for token 7 in full array [0 .. 19]
// Occurrences of 7: indices 0, 2, 7, 10, 11, 14, 17, 18 (Total: 8)
const freq7 = wtrf.frequency(0, tokenSeq.length - 1, 7);
console.log('✓ Test 1: Full range frequency of token 7: ' + freq7 + ' (expected: 8)');
if (freq7 !== 8) {
  throw new Error('Exact frequency query failed for token 7: expected 8, got ' + freq7);
}

// Test 2: Exact frequency query for token 42 in subrange [3 .. 12]
// Subrange: [19, 42, 42, 85, 7, 42, 99, 7, 7, 42] -> 42 appears 4 times (indices 4, 5, 8, 12)
const freq42Sub = wtrf.frequency(3, 12, 42);
console.log('✓ Test 2: Subrange [3..12] frequency of token 42: ' + freq42Sub + ' (expected: 4)');
if (freq42Sub !== 4) {
  throw new Error('Subrange frequency query failed: expected 4, got ' + freq42Sub);
}

// Test 3: Range Heavy Hitters with threshold tau = 5 across full array [0 .. 19]
// Tokens with count >= 5: 7 (count 8), 42 (count 7)
const hh = wtrf.rangeHeavyHitters(0, tokenSeq.length - 1, 5);
console.log('✓ Test 3: Range Heavy Hitters with count >= 5: ' + JSON.stringify(hh));
if (hh.length !== 2 || hh[0].value !== 7 || hh[0].count !== 8 || hh[1].value !== 42 || hh[1].count !== 7) {
  throw new Error('Range Heavy Hitters query failed');
}

// Test 4: Write verification report
const report = {
  experiment: 'wavelet_tree_range_freq',
  phase: 477,
  timestamp: new Date().toISOString(),
  sequenceLength: tokenSeq.length,
  token7Frequency: freq7,
  token42SubrangeFrequency: freq42Sub,
  heavyHittersThreshold5: hh,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_WAVELET_TREE_RANGE_FREQ_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_WAVELET_TREE_RANGE_FREQ_REPORT.json');

console.log('All Wavelet Tree Range Frequency tests passed successfully!');
