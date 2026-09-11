const { ABCIApplication, ABCIConsensusCoordinator } = require('../lib/tendermint_abci_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Tendermint-ABCI Consensus Engine...');
const app = new ABCIApplication();
const coord = new ABCIConsensusCoordinator(app);

// Test 1: InitChain
const init = app.initChain({ merchant_vault: 0.00 });
if (init.code !== 0 || !init.appHash) throw new Error('InitChain failed');
console.log('✓ Test 1: ABCI InitChain initialized with appHash: ' + init.appHash.slice(0, 10) + '...');

// Test 2: CheckTx mempool gating
const invalidTx = { type: 'AUTONOMOUS', spendEur: 10.00 };
const checkInvalid = app.checkTx(invalidTx);
if (checkInvalid.code === 0) throw new Error('Autonomous spend violation was not caught in CheckTx');

const validTx = { type: 'COMMERCIAL_SETTLEMENT', amountEur: 5.00, recipient: 'merchant_vault' };
const checkValid = app.checkTx(validTx);
if (checkValid.code !== 0) throw new Error('Valid transaction failed CheckTx');
console.log('✓ Test 2: CheckTx correctly gated autonomous spend invariant vs valid commercial revenue');

// Test 3: Execute Block (BeginBlock -> DeliverTx -> EndBlock -> Commit)
const blockRes = coord.executeBlock(1, 'val_0', [validTx]);
if (blockRes.deliverResults[0].code !== 0) throw new Error('DeliverTx failed');
if (app.state.accounts.get('merchant_vault') !== 5.00) throw new Error('Merchant balance mismatch');
console.log('✓ Test 3: Block 1 committed; merchant balance updated to €5.00 (AppHash: ' + blockRes.appHash.slice(0, 10) + '...)');

// Test 4: Write verification report
const report = {
  experiment: 'tendermint_abci_engine',
  phase: 447,
  timestamp: new Date().toISOString(),
  finalHeight: app.height,
  latestAppHash: app.appHash,
  settledMerchantBalanceEur: app.state.accounts.get('merchant_vault'),
  totalDeliveredTxs: app.state.transactionLog.length,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_TENDERMINT_ABCI_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_TENDERMINT_ABCI_REPORT.json');

console.log('All Tendermint-ABCI tests passed successfully!');
