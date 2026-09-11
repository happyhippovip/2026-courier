const { SimHash } = require('../lib/simhash_hamming_evaluator');
const fs = require('fs');
const path = require('path');

console.log('Testing SimHash Hamming Distance Evaluator...');
const simhash = new SimHash(64);

// Context Doc A: Baseline sequence of 50 tokens
const docA = [];
for (let i = 0; i < 50; i++) docA.push('token_system_core_' + i);

// Context Doc B: Identical to Doc A except 1 single token changed (near-duplicate)
const docB = docA.slice();
docB[25] = 'token_system_core_modified';

// Context Doc C: Completely unrelated random tokens
const docC = [];
for (let i = 0; i < 50; i++) docC.push('unrelated_topic_stream_' + i);

const fpA = simhash.computeSimHash(docA);
const fpB = simhash.computeSimHash(docB);
const fpC = simhash.computeSimHash(docC);

// Test 1: Identical document distance = 0
const distSelf = simhash.hammingDistance(fpA, fpA);
if (distSelf !== 0) throw new Error('Self distance must be 0, got ' + distSelf);
console.log('✓ Test 1: Self distance = 0 bits verified');

// Test 2: Near-duplicate distance should be very small (<= 5 bits out of 64)
const distNear = simhash.hammingDistance(fpA, fpB);
console.log('✓ Test 2: Near-duplicate document distance: ' + distNear + ' bits (expected <= 5)');
if (distNear > 5) throw new Error('Near-duplicate distance too large: ' + distNear);

// Test 3: Unrelated document distance should be around ~32 bits (50% bit flip)
const distUnrelated = simhash.hammingDistance(fpA, fpC);
console.log('✓ Test 3: Unrelated document distance: ' + distUnrelated + ' bits (expected ~32)');
if (distUnrelated < 15 || distUnrelated > 49) {
  throw new Error('Unrelated distance outside expected distribution: ' + distUnrelated);
}

// Test 4: Write verification report
const report = {
  experiment: 'simhash_hamming_evaluator',
  phase: 433,
  timestamp: new Date().toISOString(),
  bits: 64,
  selfDistance: distSelf,
  nearDuplicateDistance: distNear,
  unrelatedDistance: distUnrelated,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_SIMHASH_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_SIMHASH_REPORT.json');

console.log('All SimHash Evaluator tests passed successfully!');
