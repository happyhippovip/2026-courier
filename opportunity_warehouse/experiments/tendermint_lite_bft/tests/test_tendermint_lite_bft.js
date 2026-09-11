const { TendermintLiteBFT } = require('../lib/tendermint_lite_bft');
const fs = require('fs');
const path = require('path');

console.log('Testing Tendermint-Lite BFT Consensus Engine...');
const validators = ['val_0', 'val_1', 'val_2', 'val_3'];
const tm = new TendermintLiteBFT(validators, 1);

// Test 1: Propose block at Height 1
const blockPayload = { action: 'SETTLE_TRANSACTION_EUR5', recipient: 'merchant_vault' };
const proposal = tm.proposeBlock('val_0', blockPayload);
if (!proposal || !proposal.hash) throw new Error('Proposal failed');
console.log('✓ Test 1: Validator val_0 proposed block at height 1 (hash: ' + proposal.hash.slice(0, 10) + '...)');

// Test 2: Prevote phase with quorum 2f+1=3
tm.castPrevote('val_0', proposal.hash);
tm.castPrevote('val_1', proposal.hash);
const v3 = tm.castPrevote('val_2', proposal.hash);
if (v3 < 3) throw new Error('Expected quorum prevotes >= 3');
if (tm.step !== 'PRECOMMIT') throw new Error('Expected step to advance to PRECOMMIT');
console.log('✓ Test 2: Prevote phase reached quorum 3/4; advanced state to PRECOMMIT');

// Test 3: Precommit phase with quorum 2f+1=3
tm.castPrecommit('val_0', proposal.hash);
tm.castPrecommit('val_1', proposal.hash);
const c3 = tm.castPrecommit('val_2', proposal.hash);
if (c3 < 3) throw new Error('Expected quorum precommits >= 3');
if (tm.height !== 2) throw new Error('Expected height to advance to 2 upon commit');
console.log('✓ Test 3: Precommit reached quorum; block successfully committed; height advanced to 2');

// Test 4: Verify committed chain
const chain = tm.getCommittedChain();
if (chain.length !== 1 || chain[0].data.action !== 'SETTLE_TRANSACTION_EUR5') {
  throw new Error('Chain commit record invalid');
}
console.log('✓ Test 4: Verified committed chain ledger with 1 immutable block');

// Test 5: Write verification report
const report = {
  experiment: 'tendermint_lite_bft',
  phase: 415,
  timestamp: new Date().toISOString(),
  totalValidators: 4,
  quorum: 3,
  committedChainLength: chain.length,
  headHeight: tm.height,
  latestCommittedBlock: chain[0],
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_TENDERMINT_LITE_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 5: Evidence report written to SAMPLE_TENDERMINT_LITE_REPORT.json');

console.log('All Tendermint-Lite BFT tests passed successfully!');
