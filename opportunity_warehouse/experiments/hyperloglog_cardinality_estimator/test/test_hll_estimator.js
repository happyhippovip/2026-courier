const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { HyperLogLogEstimator } = require('../lib/hll_estimator');

const hll = new HyperLogLogEstimator(6); // 64 registers, ~13% theoretical error

// Test 1: Small cardinality accuracy with linear counting
const distinctSmall = [];
for (let i = 0; i < 40; i++) {
  distinctSmall.push('token_' + i);
}
hll.addTokens(distinctSmall);
const estSmall = hll.estimate();
const errSmall = Math.abs(estSmall - 40) / 40;
assert.ok(errSmall <= 0.15, 'Small stream estimate should be within 15% (got ' + estSmall + ')');
console.log('✓ Test 1: Linear counting accurate for small stream (exact: 40, estimated: ' + estSmall + ')');

// Test 2: Moderate stream cardinality (300 distinct items)
const hllModerate = new HyperLogLogEstimator(6);
for (let i = 0; i < 300; i++) {
  hllModerate.add('term_' + i);
  // Add some duplicates
  if (i % 2 === 0) hllModerate.add('term_' + i);
}
const estModerate = hllModerate.estimate();
const errModerate = Math.abs(estModerate - 300) / 300;
assert.ok(errModerate <= 0.20, 'Moderate stream estimate should be within 20% (got ' + estModerate + ')');
console.log('✓ Test 2: Moderate stream accurate (exact: 300, estimated: ' + estModerate + ')');

// Test 3: Register merge across distributed streams
const hllA = new HyperLogLogEstimator(6);
const hllB = new HyperLogLogEstimator(6);

for (let i = 0; i < 100; i++) hllA.add('shared_tok_' + i);
for (let i = 50; i < 150; i++) hllB.add('shared_tok_' + i); // 50 overlap, total 150 distinct

hllA.merge(hllB);
const estMerged = hllA.estimate();
const errMerged = Math.abs(estMerged - 150) / 150;
assert.ok(errMerged <= 0.20, 'Merged estimate should be within 20% of 150 (got ' + estMerged + ')');
console.log('✓ Test 3: HLL merge accurately reflects union cardinality (exact: 150, estimated: ' + estMerged + ')');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_HYPERLOGLOG_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  smallTest: { exact: 40, estimated: estSmall },
  moderateTest: { exact: 300, estimated: estModerate },
  mergedTest: { exact: 150, estimated: estMerged },
  stats: hllA.getStats()
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_HYPERLOGLOG_REPORT.json');

console.log('All HyperLogLog Estimator tests passed successfully!');
