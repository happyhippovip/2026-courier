const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { SaliencyDecayEngine } = require('../lib/decay_engine');

const engine = new SaliencyDecayEngine({ decayRate: 0.30, pruneThreshold: 0.25 });

// Test 1: Exponential decay over sequential turns
engine.addItem('turn_1', 'Initial greeting and user introduction', { pinned: false, tokens: 20 });
engine.addItem('pinned_core', 'CORE INVARIANT: Spend limit strictly EUR 0.00', { pinned: true, tokens: 30 });

engine.advanceTurn(); // Turn 2
engine.advanceTurn(); // Turn 3

const t1 = engine.items.find(i => i.id === 'turn_1');
const core = engine.items.find(i => i.id === 'pinned_core');

assert.ok(t1.currentWeight < 0.60, 'Unpinned item must decay over 2 turns');
assert.strictEqual(core.currentWeight, 1.0, 'Pinned item must never decay');
console.log('✓ Test 1: Saliency decay verified (unpinned decayed to ' + t1.currentWeight + ', pinned remained 1.0)');

// Test 2: Semantic reinforcement halts decay and restores saliency
engine.advanceTurn(['turn_1']); // Turn 4: reinforce turn_1
const t1Reinforced = engine.items.find(i => i.id === 'turn_1');
assert.ok(t1Reinforced.currentWeight > 0.80, 'Reinforced item should recover saliency');
console.log('✓ Test 2: Semantic reinforcement successfully restored weight to ' + t1Reinforced.currentWeight);

// Test 3: Multiple turns decay unreinforced items below prune threshold
engine.advanceTurn(); // Turn 5
engine.advanceTurn(); // Turn 6
engine.advanceTurn(); // Turn 7
engine.addItem('fresh_turn', 'Latest instruction: settle customer transaction', { pinned: false, tokens: 25 });

const pruneReport = engine.pruneToBudget(60); // budget allows core (30) + fresh (25) = 55 tokens
assert.ok(pruneReport.prunedCount >= 1, 'Cold item should be pruned');
assert.ok(engine.items.some(i => i.id === 'pinned_core'), 'Pinned core must remain');
assert.ok(engine.items.some(i => i.id === 'fresh_turn'), 'Fresh turn must remain');
console.log('✓ Test 3: Saliency budget pruning evicted ' + pruneReport.prunedCount + ' cold items, preserved core');

// Test 4: Write sample evidence report
const evidencePath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SALIENCY_DECAY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify({
  currentTurn: engine.currentTurn,
  pruneReport,
  activeItems: engine.items.map(it => ({ id: it.id, weight: it.currentWeight, pinned: it.pinned }))
}, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_SALIENCY_DECAY_REPORT.json');

console.log('All Saliency Decay Engine tests passed successfully!');
