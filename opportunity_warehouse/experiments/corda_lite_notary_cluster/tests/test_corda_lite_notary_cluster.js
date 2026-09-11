const { CordaLiteNotaryCluster, StateRef, NotarizationRequest } = require('../lib/corda_lite_notary_cluster');
const fs = require('fs');
const path = require('path');

console.log('Testing Corda-Lite Asynchronous Notary Cluster Engine...');
const notaries = ['notary_0', 'notary_1', 'notary_2', 'notary_3'];
const cluster = new CordaLiteNotaryCluster(notaries, 1);

// Test 1: Successful notarization of valid transaction
const input1 = new StateRef('0x genesis_tx', 0);
const input2 = new StateRef('0x genesis_tx', 1);
const req1 = new NotarizationRequest('0x tx_alpha_settlement', [input1, input2], [{ value: 5.00 }], Date.now() + 10000);

const res1 = cluster.notarizeTransaction(req1);
console.log('✓ Test 1: Transaction 1 successfully notarized with certId: ' + res1.certificate.certId.slice(0, 10) + '...');
if (!res1.success || res1.certificate.signatures.length < 3) {
  throw new Error('Notarization 1 failed');
}

// Test 2: Invariant check - states are recorded as consumed
if (!cluster.isStateConsumed(input1.id) || !cluster.isStateConsumed(input2.id)) {
  throw new Error('Input states not marked consumed after notarization');
}
console.log('✓ Test 2: Input states permanently recorded as consumed in spend registry');

// Test 3: Double-spend detection
// Attempt to spend input1 again in a competing transaction
const input3 = new StateRef('0x other_tx', 0);
const reqDoubleSpend = new NotarizationRequest('0x tx_malicious_double_spend', [input1, input3], [{ value: 10.00 }], Date.now() + 10000);

const res2 = cluster.notarizeTransaction(reqDoubleSpend);
console.log('✓ Test 3: Competing double-spend rejected with status: ' + res2.error);
if (res2.success || res2.details[0].status !== 'DOUBLE_SPEND_CONFLICT') {
  throw new Error('Double-spend conflict was not correctly detected and prevented');
}

// Test 4: Write verification report
const report = {
  experiment: 'corda_lite_notary_cluster',
  phase: 471,
  timestamp: new Date().toISOString(),
  clusterSize: 4,
  quorumRequired: 3,
  initialTransactionNotarized: res1.success,
  consumedStates: [input1.id, input2.id],
  doubleSpendDetected: !res2.success,
  conflictsReported: res2.details.length,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_CORDA_LITE_NOTARY_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_CORDA_LITE_NOTARY_REPORT.json');

console.log('All Corda-Lite Notary Cluster tests passed successfully!');
