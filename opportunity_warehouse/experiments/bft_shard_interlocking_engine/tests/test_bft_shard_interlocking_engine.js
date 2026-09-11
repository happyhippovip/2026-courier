const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BftShardInterlockingEngine } = require('../lib/bft_shard_interlocking_engine');

console.log('Testing BFT Shard Checkpoint Interlocking Consensus Engine...');
const engine = new BftShardInterlockingEngine();

// Test 1: Create Shard A Checkpoint
const cpA = engine.createInterlock('shard-A', 1, '0xrootA1', []);
assert.strictEqual(cpA.interlockId, 'IL-shard-A-E1');
console.log('✓ Test 1: Shard A checkpoint interlocked (hash:', cpA.interlockHash.substring(0, 10), '...)');

// Test 2: Create Shard B Checkpoint interlocking with Shard A
const cpB = engine.createInterlock('shard-B', 1, '0xrootB1', [{ shardId: 'shard-A', checkpointId: cpA.interlockId }]);
assert.strictEqual(cpB.peerShardReferences.length, 1);
assert.strictEqual(cpB.peerShardReferences[0].checkpointId, cpA.interlockId);
console.log('✓ Test 2: Shard B checkpoint successfully interlocked with Shard A reference');

// Test 3: Causal ancestry verification
assert.strictEqual(engine.verifyCausalAncestry(cpA.interlockId, cpB.interlockId), true);
assert.strictEqual(engine.verifyCausalAncestry(cpB.interlockId, cpA.interlockId), false);
console.log('✓ Test 3: Causal cross-shard happens-before relation verified');

const report = {
  test: 'BFT_SHARD_INTERLOCKING_ENGINE',
  passed: true,
  checkpointsCount: engine.interlockedCheckpoints.size,
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_BFT_INTERLOCKING_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 4: Evidence report written to SAMPLE_BFT_INTERLOCKING_REPORT.json');
console.log('All BFT Shard Checkpoint Interlocking Consensus tests passed successfully!');
