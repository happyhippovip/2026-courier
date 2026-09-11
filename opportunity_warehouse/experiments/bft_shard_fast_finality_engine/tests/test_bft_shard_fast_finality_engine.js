const { BFTShardFastFinalityEngine } = require('../lib/bft_shard_fast_finality_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Fast-Finality Consensus Engine...');

const validatorWeights = {
  node_0: 25,
  node_1: 25,
  node_2: 25,
  node_3: 25
};

const engine = new BFTShardFastFinalityEngine(validatorWeights, 0.75);

// Test 1: Construct proposal
const proposal1 = engine.proposeBlock('shard_0', 1, ['tx_fast_1', 'tx_fast_2']);
assert.strictEqual(proposal1.shardId, 'shard_0');
console.log('✓ Test 1: Block proposal constructed');

// Test 2: Sub-quorum rejection
const subQuorum = [{ validatorId: 'node_0', sig: 's0' }]; // 25%
const subRes = engine.evaluateFinality(proposal1, subQuorum, 100);
assert.strictEqual(subRes.finalized, false);
console.log('✓ Test 2: Sub-quorum rejection verified fail-closed');

// Test 3: Optimistic Fast-Path finality (100% quorum, 150ms latency)
const fullSigs = [
  { validatorId: 'node_0', sig: 's0' },
  { validatorId: 'node_1', sig: 's1' },
  { validatorId: 'node_2', sig: 's2' },
  { validatorId: 'node_3', sig: 's3' }
];
const fastRes = engine.evaluateFinality(proposal1, fullSigs, 150);
assert.strictEqual(fastRes.finalized, true);
assert.strictEqual(fastRes.mode, 'FAST_PATH_OPTIMISTIC');
console.log('✓ Test 3: Optimistic Fast-Path finality verified in 1 RTT (150ms)');

// Test 4: Standard BFT Fallback path (75% quorum, but high latency 500ms > 300ms)
const proposal2 = engine.proposeBlock('shard_0', 2, ['tx_fallback_1']);
const threeSigs = [
  { validatorId: 'node_0', sig: 's0' },
  { validatorId: 'node_1', sig: 's1' },
  { validatorId: 'node_2', sig: 's2' }
];
const fallbackRes = engine.evaluateFinality(proposal2, threeSigs, 500);
assert.strictEqual(fallbackRes.finalized, true);
assert.strictEqual(fallbackRes.mode, 'STANDARD_BFT_FALLBACK');
console.log('✓ Test 4: Graceful fallback to Standard BFT verified under latency spike');

// Test 5: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_FAST_FINALITY_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'bft_shard_fast_finality_engine');
assert.strictEqual(report.finalizedBlockCount, 2);
console.log('✓ Test 5: Evidence report written to SAMPLE_SHARD_FAST_FINALITY_REPORT.json');

console.log('All BFT Shard Fast-Finality Consensus Engine tests passed successfully!');
