const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { BftShardCrossLinkEngine } = require('../lib/bft_shard_crosslink_engine');

console.log('Testing BFT Shard Cross-Link Verification Engine...');
const engine = new BftShardCrossLinkEngine();

// Test 1: Cross-link submission with 3/4 quorum (75% >= 66.7%)
const cl1 = engine.submitCrossLink('shard-1', 1, '0xshard1root...', ['v1', 'v2', 'v3']);
assert.strictEqual(cl1.shardId, 'shard-1');
assert.strictEqual(cl1.epoch, 1);
assert.strictEqual(cl1.quorumRatio, 0.75);
console.log('✓ Test 1: Shard 1 Cross-link anchored with 75% quorum (hash:', cl1.crossLinkHash.substring(0, 10), '...)');

// Test 2: Reject cross-link with 2/4 quorum (50% < 66.7%)
let caughtDeficit = false;
try {
  engine.submitCrossLink('shard-2', 1, '0xshard2root...', ['v1', 'v2']);
} catch (err) {
  caughtDeficit = true;
  console.log('✓ Test 2: Insufficient cross-link quorum rejected fail-closed:', err.message);
}
assert.strictEqual(caughtDeficit, true, 'Failed to reject insufficient quorum!');

// Test 3: Retrieve latest cross-link
const latest = engine.getLatestCrossLink('shard-1');
assert.strictEqual(latest.crossLinkHash, cl1.crossLinkHash);
console.log('✓ Test 3: Latest cross-link retrieval verified');

const report = {
  test: 'BFT_SHARD_CROSSLINK_ENGINE',
  passed: true,
  anchoredShards: Array.from(engine.crossLinks.keys()),
  timestamp: new Date().toISOString()
};

fs.writeFileSync(path.join(__dirname, 'SAMPLE_BFT_CROSSLINK_REPORT.json'), JSON.stringify(report, null, 2));
console.log('✓ Test 4: Evidence report written to SAMPLE_BFT_CROSSLINK_REPORT.json');
console.log('All BFT Shard Cross-Link Verification tests passed successfully!');
