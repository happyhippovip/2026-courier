const { BTreapFilter } = require('../lib/b_treap_filter');
const fs = require('fs');
const path = require('path');

console.log('Testing B-Treap Priority Search Filter...');
const bTreap = new BTreapFilter(2);

const sampleData = [
  { key: 10, priority: 0.45 },
  { key: 25, priority: 0.92 },
  { key: 30, priority: 0.15 },
  { key: 45, priority: 0.88 },
  { key: 50, priority: 0.70 },
  { key: 65, priority: 0.99 },
  { key: 70, priority: 0.35 },
  { key: 85, priority: 0.60 },
  { key: 90, priority: 0.80 },
  { key: 105, priority: 0.20 }
];

for (const d of sampleData) {
  bTreap.insert(d.key, d.priority, 'payload_' + d.key);
}
console.log('✓ Test 1: 10 tokens inserted into B-Treap; size: ' + bTreap.size);
if (bTreap.size !== 10) throw new Error('Size mismatch');

const maxP = bTreap.getMaxPriorityInRange(20, 80);
console.log('✓ Test 2: Max priority in range [20, 80]: ' + maxP + ' (expected: 0.99)');
if (maxP !== 0.99) throw new Error('Max priority failed');

const heavyHitters = bTreap.rangePriorityQuery(20, 80, 0.85);
console.log('✓ Test 3: High-priority tokens (>= 0.85) in range: ' + JSON.stringify(heavyHitters.map(h => ({ k: h.key, p: h.priority }))));
if (heavyHitters.length !== 3 || heavyHitters[0].key !== 65 || heavyHitters[1].key !== 25 || heavyHitters[2].key !== 45) {
  throw new Error('Filtered range priority query failed');
}

const emptyRes = bTreap.rangePriorityQuery(0, 200, 1.5);
console.log('✓ Test 4: Out-of-bounds priority threshold pruned instantly');
if (emptyRes.length !== 0) throw new Error('Pruning check failed');

const report = {
  experiment: 'b_treap_filter',
  phase: 497,
  timestamp: new Date().toISOString(),
  bParameter: 2,
  totalItems: bTreap.size,
  rangeMaxTest: { range: [20, 80], maxFound: maxP },
  rangeFilterTest: { range: [20, 80], threshold: 0.85, matched: heavyHitters.length },
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_B_TREAP_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_B_TREAP_REPORT.json');

console.log('All B-Treap Filter tests passed successfully!');
