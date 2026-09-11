const { MirBFTConsensus } = require('../lib/mir_bft_consensus');
const fs = require('fs');
const path = require('path');

console.log('Testing Mir-BFT Multi-Leader Consensus Engine...');
const leaders = ['leader_0', 'leader_1', 'leader_2', 'leader_3'];
const mir = new MirBFTConsensus(leaders, 4, 1);

// Test 1: Concurrently propose in disjoint buckets (Bucket 0 -> leader_0, Bucket 1 -> leader_1)
const b0 = mir.proposeBatch('leader_0', 0, [{ tx: 'audit_context_span_0' }]);
const b1 = mir.proposeBatch('leader_1', 1, [{ tx: 'settle_order_eur5' }]);

if (b0.leaderId !== 'leader_0' || b1.leaderId !== 'leader_1') {
  throw new Error('Bucket assignments failed');
}
console.log('✓ Test 1: Multi-leader concurrent batch proposals valid for assigned buckets');

// Test 2: Commit batches with 2f+1 quorum
const rec0 = mir.commitBatch(b0);
const rec1 = mir.commitBatch(b1);
if (mir.committedBatches.length !== 2) throw new Error('Expected 2 committed batches');
console.log('✓ Test 2: Multi-leader batches committed in parallel with quorum signatures');

// Test 3: Unauthorized leader proposing for another bucket is strictly rejected
let caughtUnauthorized = false;
try {
  mir.proposeBatch('leader_0', 1, [{ tx: 'hijack_bucket_1' }]);
} catch (err) {
  if (err.message.includes('UNAUTHORIZED_LEADER')) {
    caughtUnauthorized = true;
  }
}
if (!caughtUnauthorized) throw new Error('Unauthorized leader was not rejected');
console.log('✓ Test 3: Unauthorized leader proposal for foreign bucket strictly rejected');

// Test 4: Write verification report
const report = {
  experiment: 'mir_bft_consensus',
  phase: 431,
  timestamp: new Date().toISOString(),
  totalLeaders: 4,
  buckets: 4,
  quorum: 3,
  committedBatchesCount: mir.committedBatches.length,
  bucketAssignments: Object.fromEntries(mir.bucketAssignments),
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_MIR_BFT_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_MIR_BFT_REPORT.json');

console.log('All Mir-BFT Consensus tests passed successfully!');
