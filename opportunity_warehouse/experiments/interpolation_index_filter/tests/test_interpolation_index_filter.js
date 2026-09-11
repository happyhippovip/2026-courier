const { BoundedInterpolationIndexFilter } = require('../lib/interpolation_index_filter');
const fs = require('fs');
const path = require('path');

console.log('Testing Bounded Interpolation Index Filter...');

// Synthetic sequence of 150 token keys
const keys = [];
let currentVal = 20;
for (let i = 0; i < 150; i++) {
  currentVal += Math.floor(Math.random() * 5) + 1;
  keys.push(currentVal);
}

const biFilter = new BoundedInterpolationIndexFilter(keys, 3);

// Test 1: Lookup all 150 keys
for (let i = 0; i < keys.length; i++) {
  const found = biFilter.lookup(keys[i]);
  if (found === -1 || keys[found] !== keys[i]) {
    throw new Error('Lookup failed for key: ' + keys[i] + ' at index ' + i);
  }
}
console.log('✓ Test 1: All 150 keys successfully retrieved via bounded interpolation search');

// Test 2: Boundary lookups (first, last, out-of-bounds)
const first = biFilter.lookup(keys[0]);
const last = biFilter.lookup(keys[keys.length - 1]);
const outLow = biFilter.lookup(keys[0] - 5);
const outHigh = biFilter.lookup(keys[keys.length - 1] + 5);

console.log('✓ Test 2: Boundary lookups verified: first=' + first + ', last=' + last + ', outLow=' + outLow + ', outHigh=' + outHigh);
if (first !== 0 || last !== keys.length - 1 || outLow !== -1 || outHigh !== -1) {
  throw new Error('Boundary conditions failed');
}

// Test 3: Write verification report
const report = {
  experiment: 'interpolation_index_filter',
  phase: 493,
  timestamp: new Date().toISOString(),
  stats: biFilter.getStats(),
  testedLookupsCount: 150,
  allLookupsSuccessful: true,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_INTERPOLATION_INDEX_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 3: Evidence report written to SAMPLE_INTERPOLATION_INDEX_REPORT.json');

console.log('All Bounded Interpolation Index tests passed successfully!');
