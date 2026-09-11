const { TreapIntervalUnion } = require('../lib/treap_interval_union');
const fs = require('fs');
const path = require('path');

console.log('Testing Treap Interval Union Evaluator...');
const treap = new TreapIntervalUnion();

// Test 1: Insertion
treap.insert(100, 250, 'chunk_1');
treap.insert(200, 400, 'chunk_2');
treap.insert(500, 700, 'chunk_3');
treap.insert(650, 850, 'chunk_4');
treap.insert(1000, 1200, 'chunk_5');

if (treap.size !== 5) throw new Error('Expected size 5, got ' + treap.size);
console.log('✓ Test 1: Inserted 5 overlapping and disjoint intervals into Treap');

// Test 2: Compute union intervals
const unions = treap.computeIntervalUnion();
// Expected: [100, 400], [500, 850], [1000, 1200]
if (unions.length !== 3) throw new Error('Expected 3 merged intervals, got ' + unions.length);
if (unions[0].low !== 100 || unions[0].high !== 400) throw new Error('Union 0 mismatch');
if (unions[1].low !== 500 || unions[1].high !== 850) throw new Error('Union 1 mismatch');
if (unions[2].low !== 1000 || unions[2].high !== 1200) throw new Error('Union 2 mismatch');
console.log('✓ Test 2: Successfully merged intervals into disjoint union components: ' + JSON.stringify(unions));

// Test 3: Total covered tokens
// 300 (100..400) + 350 (500..850) + 200 (1000..1200) = 850 tokens
const totalCovered = treap.totalCoveredTokens();
if (totalCovered !== 850) throw new Error('Expected 850 covered tokens, got ' + totalCovered);
console.log('✓ Test 3: Total covered tokens correctly calculated as ' + totalCovered);

// Test 4: Write verification report
const report = {
  experiment: 'treap_interval_union',
  phase: 401,
  timestamp: new Date().toISOString(),
  totalIntervals: treap.size,
  mergedUnionCount: unions.length,
  totalCoveredTokens: totalCovered,
  unionRanges: unions,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_TREAP_INTERVAL_UNION_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_TREAP_INTERVAL_UNION_REPORT.json');

console.log('All Treap Interval Union tests passed successfully!');
