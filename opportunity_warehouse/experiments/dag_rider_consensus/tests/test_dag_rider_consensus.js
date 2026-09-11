const { DAGRiderConsensusEngine } = require('../lib/dag_rider_consensus');
const fs = require('fs');
const path = require('path');

console.log('Testing DAG-Rider Asynchronous Consensus Engine...');
const validators = ['v0', 'v1', 'v2', 'v3'];
const dagRider = new DAGRiderConsensusEngine(validators, 1);

// Wave 0 consists of Rounds 1, 2, 3, 4
// Wave 0 Leader is v0 in Round 1

// Round 1 (Propose)
const r1_v0 = dagRider.addVertex('v0', 1, [], { tx: 'tx_leader_wave0' });
const r1_v1 = dagRider.addVertex('v1', 1, [], { tx: 'tx_v1_r1' });
const r1_v2 = dagRider.addVertex('v2', 1, [], { tx: 'tx_v2_r1' });
const r1_v3 = dagRider.addVertex('v3', 1, [], { tx: 'tx_v3_r1' });
console.log('✓ Test 1: Created Round 1 propose vertices for 4 validators');

// Round 2 (Vote) referencing Round 1
const r1_parents = [r1_v0.id, r1_v1.id, r1_v2.id];
const r2_v0 = dagRider.addVertex('v0', 2, r1_parents, { tx: 'tx_v0_r2' });
const r2_v1 = dagRider.addVertex('v1', 2, r1_parents, { tx: 'tx_v1_r2' });
const r2_v2 = dagRider.addVertex('v2', 2, r1_parents, { tx: 'tx_v2_r2' });
console.log('✓ Test 2: Created Round 2 vote vertices with quorum parents');

// Round 3 (Certify) referencing Round 2
const r2_parents = [r2_v0.id, r2_v1.id, r2_v2.id];
const r3_v0 = dagRider.addVertex('v0', 3, r2_parents, { tx: 'tx_v0_r3' });
const r3_v1 = dagRider.addVertex('v1', 3, r2_parents, { tx: 'tx_v1_r3' });
const r3_v2 = dagRider.addVertex('v2', 3, r2_parents, { tx: 'tx_v2_r3' });
console.log('✓ Test 3: Created Round 3 certify vertices');

// Round 4 (Wave Leader Commit Round) referencing Round 3
const r3_parents = [r3_v0.id, r3_v1.id, r3_v2.id];
const r4_v0 = dagRider.addVertex('v0', 4, r3_parents, { tx: 'tx_v0_r4' });
const r4_v1 = dagRider.addVertex('v1', 4, r3_parents, { tx: 'tx_v1_r4' });
const r4_v2 = dagRider.addVertex('v2', 4, r3_parents, { tx: 'tx_v2_r4' });
console.log('✓ Test 4: Created Round 4 commit vertices');

// Evaluate Wave 0
const wave0Result = dagRider.evaluateWave(0);
console.log('✓ Test 5: Wave 0 evaluation result: ' + JSON.stringify(wave0Result));

if (!wave0Result || !wave0Result.committed || wave0Result.supportingQuorum < 3) {
  throw new Error('DAG-Rider Wave 0 commit failed');
}

// Check causal linear ordering
const txs = dagRider.getLinearizedTransactions();
console.log('✓ Test 6: Linearized transactions in causal order: ' + JSON.stringify(txs));

if (!txs.includes('tx_leader_wave0')) {
  throw new Error('Committed wave leader transaction missing from linearized log');
}

// Invariant: Wave 0 leader must precede Round 4 transactions
const idxLeader = txs.indexOf('tx_leader_wave0');
const idxR4 = txs.indexOf('tx_v0_r4');
if (idxLeader === -1 || (idxR4 !== -1 && idxLeader > idxR4)) {
  throw new Error('Causal ordering violation in DAG-Rider');
}

// Write evidence report
const report = {
  experiment: 'dag_rider_consensus',
  phase: 467,
  timestamp: new Date().toISOString(),
  validators: 4,
  quorum: 3,
  waveEvaluated: 0,
  leaderCommitted: wave0Result.committed,
  supportingQuorumCount: wave0Result.supportingQuorum,
  totalVertices: dagRider.vertices.size,
  linearizedCount: txs.length,
  linearizedLog: txs,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_DAG_RIDER_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 7: Evidence report written to SAMPLE_DAG_RIDER_REPORT.json');

console.log('All DAG-Rider Consensus Engine tests passed successfully!');
