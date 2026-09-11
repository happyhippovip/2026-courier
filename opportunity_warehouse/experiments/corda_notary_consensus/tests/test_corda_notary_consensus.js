const { CordaNotaryConsensus, NotaryTransaction, StateRef } = require('../lib/corda_notary_consensus');
const fs = require('fs');
const path = require('path');

console.log('Testing Corda-Style Notary Service Consensus Engine...');
const notaries = ['notary_0', 'notary_1', 'notary_2'];
const notary = new CordaNotaryConsensus(notaries, 1);

// Test 1: Valid initial notarization
const input1 = new StateRef('tx_genesis_0', 0);
const input2 = new StateRef('tx_genesis_0', 1);
const tx1 = new NotaryTransaction([input1, input2], [{ amountEur: 5.00, owner: 'customer_acct' }], 'COMMERCIAL_SETTLE_EUR5', 'mac_settlement_agent');

const receipt1 = notary.notarizeTransaction(tx1);
if (!receipt1 || !receipt1.txId) throw new Error('Notarization 1 failed');
if (Object.keys(receipt1.signatures).length < 2) throw new Error('Quorum signatures missing');
console.log('✓ Test 1: Transaction notarized successfully with quorum signatures (txId: ' + receipt1.txId.slice(0, 10) + '...)');

// Test 2: Double spend prevention
const doubleSpendTx = new NotaryTransaction([input1], [{ amountEur: 5.00, owner: 'malicious_replay' }], 'COMMERCIAL_SETTLE_EUR5', 'adversary_agent');
let caughtDoubleSpend = false;
try {
  notary.notarizeTransaction(doubleSpendTx);
} catch (err) {
  if (err.message.includes('DOUBLE_SPEND_DETECTED')) {
    caughtDoubleSpend = true;
  }
}
if (!caughtDoubleSpend) throw new Error('Double spend was not detected!');
console.log('✓ Test 2: Attempted double-spend of state ' + input1.key + ' strictly rejected');

// Test 3: Unspent input succeeds
const input3 = new StateRef('tx_genesis_1', 0);
const tx3 = new NotaryTransaction([input3], [{ amountEur: 0.00, owner: 'standby_agent' }], 'STANDBY_POLL', 'windows_observer');
const receipt3 = notary.notarizeTransaction(tx3);
if (!receipt3) throw new Error('Notarization 3 failed');
console.log('✓ Test 3: Valid fresh state successfully notarized');

// Test 4: Write verification report
const report = {
  experiment: 'corda_notary_consensus',
  phase: 411,
  timestamp: new Date().toISOString(),
  totalNotaries: 3,
  quorum: 2,
  notarizedTransactionsCount: notary.notarizedLedger.size,
  spentStatesCount: notary.spentStates.size,
  doubleSpendPrevented: caughtDoubleSpend,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_CORDA_NOTARY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_CORDA_NOTARY_REPORT.json');

console.log('All Corda Notary Consensus tests passed successfully!');
