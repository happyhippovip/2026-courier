const { BFTShardDualQuorumEngine } = require('../lib/bft_shard_dual_quorum_engine');
const assert = require('assert');
const path = require('path');

console.log('Testing BFT Shard Dual-Quorum Consensus Engine...');

const shardValidators = {
  shard_alpha: { v_a1: 50, v_a2: 50 },
  shard_beta:  { v_b1: 50, v_b2: 50 }
};

const engine = new BFTShardDualQuorumEngine(shardValidators);

// Test 1: Propose cross-shard transaction
const tx = engine.proposeCrossShardTx('tx_cross_001', 'shard_alpha', 'shard_beta', 1000);
assert.strictEqual(tx.status, 'PROPOSED');
console.log('✓ Test 1: Cross-shard transfer proposed');

// Test 2: Premature finalize attempt fails
const preRes = engine.finalizeDualQuorumCommit('tx_cross_001');
assert.strictEqual(preRes.finalized, false);
assert.strictEqual(preRes.reason, 'MISSING_DUAL_QUORUM_PROOF');
console.log('✓ Test 2: Premature finalize rejected fail-closed');

// Test 3: Certify origin shard with 2f+1 quorum (100% weight)
const origSigs = [{ validatorId: 'v_a1' }, { validatorId: 'v_a2' }];
const origRes = engine.certifyOriginShard('tx_cross_001', origSigs);
assert.strictEqual(origRes.certified, true);
console.log('✓ Test 3: Origin shard quorum certified');

// Test 4: Still fails with only origin QC
const partialRes = engine.finalizeDualQuorumCommit('tx_cross_001');
assert.strictEqual(partialRes.finalized, false);
assert.strictEqual(partialRes.hasOriginQC, true);
assert.strictEqual(partialRes.hasDestQC, false);
console.log('✓ Test 4: Partial single-quorum commit prevented');

// Test 5: Certify destination shard with 2f+1 quorum
const destSigs = [{ validatorId: 'v_b1' }, { validatorId: 'v_b2' }];
const destRes = engine.certifyDestShard('tx_cross_001', destSigs);
assert.strictEqual(destRes.certified, true);
console.log('✓ Test 5: Destination shard quorum certified');

// Test 6: Finalize dual-quorum commit (2QC)
const finalRes = engine.finalizeDualQuorumCommit('tx_cross_001');
assert.strictEqual(finalRes.finalized, true);
assert.strictEqual(engine.committedTxs.length, 1);
console.log('✓ Test 6: Global atomic commit achieved with verified Dual-Quorum Proof (2QC)');

// Test 7: Export evidence report
const reportPath = path.join(__dirname, '..', '..', '..', 'evidence', 'SAMPLE_SHARD_DUAL_QUORUM_REPORT.json');
const report = engine.exportEvidenceReport(reportPath);
assert.strictEqual(report.subsystem, 'bft_shard_dual_quorum_engine');
assert.strictEqual(report.totalCommitted, 1);
console.log('✓ Test 7: Evidence report written to SAMPLE_SHARD_DUAL_QUORUM_REPORT.json');

console.log('All BFT Shard Dual-Quorum Consensus Engine tests passed successfully!');
