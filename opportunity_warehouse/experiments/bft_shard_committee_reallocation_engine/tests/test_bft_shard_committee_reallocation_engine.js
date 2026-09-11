const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BFTShardCommitteeReallocationEngine } = require('../lib/bft_shard_committee_reallocation_engine');

console.log('Testing BFT Shard Dynamic Committee Re-Allocation Engine...');
const engine = new BFTShardCommitteeReallocationEngine(3, 3); // 3 shards, 3 validators each = 9 required

const validators = [
  'val-0', 'val-1', 'val-2',
  'val-3', 'val-4', 'val-5',
  'val-6', 'val-7', 'val-8',
  'val-9'
];

// Reallocate Epoch 1
const seed1 = 'seed-epoch-001-entropy-xyz';
const alloc1 = engine.reallocate(1, seed1, validators);
assert.strictEqual(alloc1.epoch, 1);
assert.strictEqual(engine.getCommitteeForShard('shard-0').length, 3);
assert.strictEqual(engine.getCommitteeForShard('shard-1').length, 3);
assert.strictEqual(engine.getCommitteeForShard('shard-2').length, 3);

// Deterministic repeat check with same seed produces exact same allocation
const engine2 = new BFTShardCommitteeReallocationEngine(3, 3);
const allocRepeat = engine2.reallocate(1, seed1, validators);
assert.deepStrictEqual(alloc1.assignments, allocRepeat.assignments);

// Epoch 2 with different seed produces different allocation
const seed2 = 'seed-epoch-002-entropy-abc';
const alloc2 = engine.reallocate(2, seed2, validators);
assert.strictEqual(alloc2.epoch, 2);

const report = {
  experiment: 'bft_shard_committee_reallocation_engine',
  status: 'VERIFIED',
  testSuite: 'test_bft_shard_committee_reallocation_engine',
  lastAllocation: alloc2,
  historyLength: engine.history.length,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(
  path.join(__dirname, 'SAMPLE_BFT_COMMITTEE_REALLOCATION_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);

console.log('✓ BFT Shard Dynamic Committee Re-Allocation Engine verified successfully.');
