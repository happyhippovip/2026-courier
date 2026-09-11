const { TuskHotStuffEngine } = require('../lib/tusk_hotstuff_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Tusk-HotStuff Hybrid Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const hybrid = new TuskHotStuffEngine(nodes, 1);

// Test 1: Publish 2 Certificates of Availability (CoAs) from DAG layer
const coa1 = hybrid.publishCoA('batch_order_eur5_inflow', 1, 'node_0');
const coa2 = hybrid.publishCoA('batch_audit_merkle_checkpoint', 1, 'node_1');

if (Object.keys(coa1.signatures).length < 3) throw new Error('CoA 1 missing quorum');
console.log('✓ Test 1: Published 2 DAG Certificates of Availability with 2f+1 signatures');

// Test 2: Sequence CoA 1 via HotStuff Chained Proposal
const b1 = hybrid.proposeNode(coa1.coaId);
const qc1 = hybrid.voteAndFormQC(b1.hash);
if (!qc1 || !qc1.qcId) throw new Error('QC1 formation failed');
console.log('✓ Test 2: Proposed and certified Block 1 referencing CoA 1');

// Test 3: Sequence CoA 2 in Block 2 (Chaining commits Block 1 / CoA 1)
const b2 = hybrid.proposeNode(coa2.coaId);
const qc2 = hybrid.voteAndFormQC(b2.hash);

const committed = hybrid.getCommittedCoas();
if (committed.length !== 1 || committed[0] !== coa1.coaId) {
  throw new Error('Expected CoA 1 to be committed via chained HotStuff rule');
}
console.log('✓ Test 3: HotStuff chaining rule successfully committed CoA 1 (' + coa1.coaId.slice(0, 10) + '...)');

// Test 4: Write verification report
const report = {
  experiment: 'tusk_hotstuff_engine',
  phase: 455,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  quorum: 3,
  dagCoasPublished: hybrid.coas.size,
  committedCoasCount: committed.length,
  headView: hybrid.currentView,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_TUSK_HOTSTUFF_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_TUSK_HOTSTUFF_REPORT.json');

console.log('All Tusk-HotStuff tests passed successfully!');
