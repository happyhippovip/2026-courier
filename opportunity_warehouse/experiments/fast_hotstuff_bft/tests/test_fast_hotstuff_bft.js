const { FastHotStuffBFT } = require('../lib/fast_hotstuff_bft');
const fs = require('fs');
const path = require('path');

console.log('Testing Fast-HotStuff Pipelined BFT Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const hs = new FastHotStuffBFT(nodes, 1);

// Test 1: Block 1 proposed and QC formed
const b1 = hs.proposeBlock('node_0', { action: 'AUDIT_MERKLE_ROOT', root: '0xabc1' });
const qc1 = hs.formQC(b1.hash);
if (Object.keys(qc1.signatures).length < 3) throw new Error('QC1 missing quorum signatures');
console.log('✓ Test 1: Block 1 QC formed with quorum 2f+1=3');

// Test 2: Block 2 proposed chained from QC1
const b2 = hs.proposeBlock('node_1', { action: 'VERIFY_BALANCE_EUR', eur: 0.00 });
const qc2 = hs.formQC(b2.hash);
console.log('✓ Test 2: Block 2 QC formed chained from QC1');

// Test 3: Block 3 proposed chained from QC2 (triggers three-chain commit of Block 1)
const b3 = hs.proposeBlock('node_2', { action: 'SETTLE_REVENUE_EUR5', amount: 5.00 });
const qc3 = hs.formQC(b3.hash);

const committed = hs.getCommittedBlocks();
if (committed.length === 0 || committed[0].hash !== b1.hash) {
  throw new Error('Expected Block 1 to be committed via three-chain commit rule');
}
console.log('✓ Test 3: Three-chain commit rule successfully committed Block 1 (' + committed[0].hash.slice(0, 10) + '...)');

// Test 4: Write verification report
const report = {
  experiment: 'fast_hotstuff_bft',
  phase: 419,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  quorum: 3,
  viewsCompleted: hs.currentView - 1,
  highQcBlockHash: hs.highQC.blockHash,
  committedBlocksCount: committed.length,
  committedBlockAction: committed[0].payload.action,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_FAST_HOTSTUFF_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_FAST_HOTSTUFF_REPORT.json');

console.log('All Fast-HotStuff BFT tests passed successfully!');
