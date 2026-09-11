const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { TemporalDecayEngine } = require('../lib/temporal_decay');

console.log('--- Testing Temporal Decay & Semantic Forgetfulness Engine ---');

const engine = new TemporalDecayEngine(4); // 4-turn half-life

// Add memories
engine.addMemory('sec_rule', 'Zero spend policy invariant', 1, { isPermanent: true });
engine.addMemory('intermediate_draft', 'Initial unfinished pseudocode draft for testing', 1, { halfLifeTurns: 2 });
engine.addMemory('user_chat_note', 'User mentioned preference for dark mode theme', 1, { halfLifeTurns: 4 });

// Test 1: Permanent memory retains weight 1.0 regardless of turn
const secWeight = engine.calculateRetentionWeight(engine.memories.get('sec_rule'), 20);
assert.strictEqual(secWeight, 1.0, 'Permanent memory must never decay');
console.log('✓ Assertion 1 Passed: Permanent anchor memory retained at weight 1.0 across 20 turns');

// Test 2: Exponential half-life decay calculation
// Turn 5 is 4 turns after turn 1 -> exactly 1 half life -> weight should be 0.50
const noteWeight = engine.calculateRetentionWeight(engine.memories.get('user_chat_note'), 5);
assert.strictEqual(noteWeight, 0.50, 'Weight after 1 half-life must be 0.50');
console.log('✓ Assertion 2 Passed: Exponential half-life decay computed accurately (W=' + noteWeight + ')');

// Test 3: Superceded state acceleration and eviction at turn 10
engine.markSuperceded('intermediate_draft');
const supercededWeight = engine.calculateRetentionWeight(engine.memories.get('intermediate_draft'), 10);
assert.strictEqual(supercededWeight, 0.0, 'Superceded memory weight must drop immediately to 0.0');

// At turn 10: user_chat_note age = 9 turns -> 2^(-9/4) = 0.21 < 0.25 threshold -> evicted
const compaction = engine.compactMemories(10, 0.25);
assert.strictEqual(compaction.retainedCount, 1, 'Only permanent rule should be retained at turn 10');
assert.strictEqual(compaction.evictedCount, 2, '2 decayed/superceded memories evicted');
assert.ok(compaction.savingsPercent > 40, 'Compaction must save tokens');
console.log('✓ Assertion 3 Passed: Temporal decay evicted expired memories (' + compaction.savingsPercent + '% saved)');

// Test 4: Export evidence JSON
const evidencePath = path.resolve(__dirname, '../../../evidence/SAMPLE_TEMPORAL_DECAY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(compaction, null, 2), 'utf8');
assert.ok(fs.existsSync(evidencePath), 'Evidence report must exist');
console.log('✓ Assertion 4 Passed: Evidence exported to SAMPLE_TEMPORAL_DECAY_REPORT.json');

console.log('All 4 Temporal Decay Engine tests passed successfully!');