const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { VirtualShardMigrator } = require('./lib/virtual_shard_migrator');

console.log('Testing Virtual Shard Migrator Engine...');

const migrator = new VirtualShardMigrator();
const s1 = migrator.createInitialShard(0, 1000, 'node-primary');

// Test 1: Initial shard state
assert.strictEqual(migrator.shards.get(s1).ownerNode, 'node-primary');
assert.strictEqual(migrator.shards.get(s1).count, 0);
console.log('✓ Test 1: Initial shard created spanning range [0, 1000]');

// Test 2: Hotspot accumulation triggers bisection split
let splitResult = null;
for (let i = 0; i < 100; i++) {
  splitResult = migrator.recordWrite(s1);
}
assert.ok(splitResult !== null);
assert.strictEqual(splitResult.status, 'SPLIT_COMPLETED');
assert.strictEqual(migrator.shards.has(s1), false); // Parent deleted
assert.strictEqual(migrator.shards.size, 2); // 2 children active
console.log('✓ Test 2: Hotspot write threshold triggered automated bisection split into 2 shards');

// Test 3: Write sample evidence report
const report = {
  timestamp: new Date().toISOString(),
  phase: 347,
  component: 'virtual_shard_migrator',
  splitDetails: splitResult,
  activeShardsCount: migrator.shards.size,
  hotspotMitigationVerified: true,
  verification: '100% PASS'
};

const evidenceDir = path.join(__dirname, '..', '..', 'evidence');
fs.writeFileSync(
  path.join(evidenceDir, 'SAMPLE_VIRTUAL_SHARD_MIGRATOR_REPORT.json'),
  JSON.stringify(report, null, 2),
  'utf8'
);
console.log('✓ Test 3: Evidence report written to SAMPLE_VIRTUAL_SHARD_MIGRATOR_REPORT.json');
console.log('All Virtual Shard Migrator tests passed successfully!');
