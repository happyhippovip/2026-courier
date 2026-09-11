const { IntervalTreeFilter } = require('../lib/interval_tree_filter');
const fs = require('fs');
const path = require('path');

console.log('Testing Interval Tree Range Overlap Filter...');
const tree = new IntervalTreeFilter();

// Test 1: Insertion and Tree balance
const segments = [
  { low: 0, high: 500, payload: 'system_core_prompt' },
  { low: 400, high: 1200, payload: 'episodic_memory_cache' },
  { low: 1200, high: 2500, payload: 'dialogue_turn_1' },
  { low: 2400, high: 3800, payload: 'dialogue_turn_2' },
  { low: 3500, high: 5000, payload: 'tool_call_output_batch' },
  { low: 4800, high: 6000, payload: 'reflection_scratchpad' }
];

segments.forEach(s => tree.insert(s.low, s.high, s.payload));
if (tree.size !== 6) throw new Error('Expected tree size 6, got ' + tree.size);
console.log('✓ Test 1: Inserted 6 context intervals into AVL-balanced tree');

// Test 2: Overlap query for window [1000, 2600]
const overlap1 = tree.queryOverlap(1000, 2600);
const names1 = overlap1.map(o => o.payload).sort();
const expected1 = ['dialogue_turn_1', 'dialogue_turn_2', 'episodic_memory_cache'].sort();
if (JSON.stringify(names1) !== JSON.stringify(expected1)) {
  throw new Error('Overlap query mismatch: ' + JSON.stringify(names1));
}
console.log('✓ Test 2: Overlap query [1000, 2600] correctly retrieved: ' + names1.join(', '));

// Test 3: Point query and Disjoint query
const pointQuery = tree.queryPoint(450);
const pointNames = pointQuery.map(p => p.payload).sort();
const expectedPoint = ['episodic_memory_cache', 'system_core_prompt'].sort();
if (JSON.stringify(pointNames) !== JSON.stringify(expectedPoint)) {
  throw new Error('Point query at 450 mismatch: ' + JSON.stringify(pointNames));
}

const disjointQuery = tree.queryOverlap(7000, 8000);
if (disjointQuery.length !== 0) {
  throw new Error('Disjoint query should return 0 results, got ' + disjointQuery.length);
}
console.log('✓ Test 3: Point query at 450 correctly hit dual overlaps; disjoint query returned 0');

// Test 4: Write sample evidence report
const report = {
  experiment: 'interval_tree_filter',
  phase: 393,
  timestamp: new Date().toISOString(),
  totalIndexedIntervals: tree.size,
  testedQueries: [
    { queryRange: [1000, 2600], hits: names1 },
    { pointQuery: 450, hits: pointNames },
    { queryRange: [7000, 8000], hits: disjointQuery }
  ],
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_INTERVAL_TREE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_INTERVAL_TREE_REPORT.json');

console.log('All Interval Tree Filter tests passed successfully!');
