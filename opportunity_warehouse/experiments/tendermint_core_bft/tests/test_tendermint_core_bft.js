const { TendermintCoreBFT } = require('../lib/tendermint_core_bft');
const fs = require('fs');
const path = require('path');

console.log('Testing Tendermint-Core BFT Consensus Engine...');
const validators = ['val_0', 'val_1', 'val_2', 'val_3'];
const tmc = new TendermintCoreBFT(validators, 1);

// Test 1: Propose by correct round-robin proposer
const p0 = tmc.getProposer(0);
const proposal = tmc.propose(p0, { tx: 'commit_zkcp_escrow_eur5' });
if (!proposal || !proposal.proposalHash) throw new Error('Proposal failed');
console.log('✓ Test 1: Designated proposer ' + p0 + ' proposed block for round 0');

// Test 2: POL (Proof of Lock) formed via 2f+1 prevotes
tmc.recordPrevote('val_0', 1, 0, proposal.proposalHash);
tmc.recordPrevote('val_1', 1, 0, proposal.proposalHash);
const polCount = tmc.recordPrevote('val_2', 1, 0, proposal.proposalHash);

if (polCount < 3 || tmc.lockedValue !== proposal.proposalHash) {
  throw new Error('Proof of Lock (POL) failed');
}
console.log('✓ Test 2: Proof of Lock formed (lockedValue: ' + tmc.lockedValue.slice(0, 10) + '...)');

// Test 3: Commit formed via 2f+1 precommits
tmc.recordPrecommit('val_0', 1, 0, proposal.proposalHash);
tmc.recordPrecommit('val_1', 1, 0, proposal.proposalHash);
const precommitCount = tmc.recordPrecommit('val_2', 1, 0, proposal.proposalHash);

if (tmc.height !== 2 || tmc.committedLedger.length !== 1) {
  throw new Error('Block commit failed');
}
console.log('✓ Test 3: Block successfully committed; height advanced to 2');

// Test 4: Write verification report
const report = {
  experiment: 'tendermint_core_bft',
  phase: 439,
  timestamp: new Date().toISOString(),
  totalValidators: 4,
  quorum: 3,
  committedBlocks: tmc.committedLedger.length,
  headHeight: tmc.height,
  latestCommit: tmc.committedLedger[0],
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_TENDERMINT_CORE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_TENDERMINT_CORE_REPORT.json');

console.log('All Tendermint-Core BFT tests passed successfully!');
