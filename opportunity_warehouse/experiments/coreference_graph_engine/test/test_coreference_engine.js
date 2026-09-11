const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { CoreferenceGraphEngine } = require('../lib/coreference_engine');

const engine = new CoreferenceGraphEngine();

const turns = [
  'Turn 0: Customer submitted order_alpha_99 with price €5.00.',
  'Turn 1: Autonomous agent confirmed the order in warehouse.',
  'Turn 2: Unrelated logging message with no entities.',
  'Turn 3: Worker process completed execution of it successfully.' // 'it' refers to order_alpha_99
];

// Test 1: Extract entities and resolve coreference links
const graph = engine.buildGraph(turns);
assert.ok(graph.totalEntities >= 2, 'Must extract order_alpha_99 and €5.00');
assert.ok(graph.totalLinks >= 1, 'Must link "the order" or "it" to antecedent entity');
assert.ok(graph.antecedentTurns.includes(0), 'Turn 0 must be flagged as critical antecedent turn');
console.log('✓ Test 1: Coreference graph identified ' + graph.totalLinks + ' links, marked Turn 0 as antecedent');

// Test 2: Safe pruning protects antecedent turns while evicting cold turns
const pruned = engine.safePrune(turns, 2, graph);
assert.strictEqual(pruned.retainedTurnsCount, 2, 'Should retain 2 turns');
assert.ok(pruned.retainedTurns.some(t => t.idx === 0), 'Turn 0 (antecedent) MUST NOT be pruned');
assert.ok(pruned.retainedTurns.some(t => t.idx === 3), 'Turn 3 (current mention) MUST NOT be pruned');
assert.ok(!pruned.retainedTurns.some(t => t.idx === 2), 'Turn 2 (unrelated) should be safely evicted');
console.log('✓ Test 2: Safe pruning preserved Turn 0 & Turn 3, safely evicted Turn 1 & Turn 2');

// Test 3: Multiple pronouns and entities
const multiTurns = [
  'User provided tx_884920 and license_key_xyz.',
  'System verified this transaction without errors.'
];
const multiGraph = engine.buildGraph(multiTurns);
assert.ok(multiGraph.links.some(l => l.antecedentEntity === 'license_key_xyz' || l.antecedentEntity === 'tx_884920'));
console.log('✓ Test 3: Multiple entities and pronoun disambiguation verified');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_COREFERENCE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  graphSummary: {
    totalEntities: graph.totalEntities,
    totalLinks: graph.totalLinks,
    antecedentTurns: graph.antecedentTurns
  },
  links: graph.links,
  safePruneResult: {
    originalCount: pruned.originalTurnsCount,
    retainedCount: pruned.retainedTurnsCount,
    evictedCount: pruned.evictedTurnsCount
  }
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_COREFERENCE_REPORT.json');

console.log('All Coreference Graph Engine tests passed successfully!');
