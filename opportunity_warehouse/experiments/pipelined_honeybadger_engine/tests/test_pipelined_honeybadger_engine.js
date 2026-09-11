const { PipelinedHoneyBadgerEngine } = require('../lib/pipelined_honeybadger_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Pipelined HoneyBadger Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const engine = new PipelinedHoneyBadgerEngine(nodes, 1);

// Test 1: Finalize Epoch 1
const prop1 = {
  node_0: ['tx_settlement_eur5', 'tx_token_alpha'],
  node_1: ['tx_token_beta'],
  node_2: ['tx_token_gamma'],
  node_3: ['tx_token_delta']
};

const res1 = engine.processEpoch(prop1);
console.log('✓ Test 1: Epoch 1 successfully committed; cert: ' + res1.epochCertificate.slice(0, 8) + '...');
if (res1.batchesIncludedCount !== 3 || !res1.orderedTransactions.includes('tx_settlement_eur5')) {
  throw new Error('Epoch 1 commit failed');
}

// Test 2: Finalize Epoch 2
const prop2 = {
  node_0: ['tx_epoch2_a'],
  node_1: ['tx_epoch2_b'],
  node_2: ['tx_epoch2_c']
};

const res2 = engine.processEpoch(prop2);
console.log('✓ Test 2: Epoch 2 successfully committed; total epochs: ' + engine.getCommittedEpochs().length);
if (engine.getCommittedEpochs().length !== 2) {
  throw new Error('Epoch tracking failed');
}

// Test 3: Write verification report
const report = {
  experiment: 'pipelined_honeybadger_engine',
  phase: 499,
  timestamp: new Date().toISOString(),
  nodes: 4,
  quorum: 3,
  epochsCommitted: engine.getCommittedEpochs().length,
  epoch1Result: res1,
  epoch2Result: res2,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_PIPELINED_HONEYBADGER_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 3: Evidence report written to SAMPLE_PIPELINED_HONEYBADGER_REPORT.json');

console.log('All Pipelined HoneyBadger Consensus tests passed successfully!');
