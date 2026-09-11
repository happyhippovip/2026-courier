const { NarwhalMempoolEngine } = require('../lib/narwhal_mempool_engine');
const fs = require('fs');
const path = require('path');

console.log('Testing Narwhal Mempool Dissemination Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const engine = new NarwhalMempoolEngine(nodes, 1);

// Test 1: Submit batch of transactions
const txs = [
  { action: 'context_prune', target: 'span_0_400' },
  { action: 'rebalance_cache', partition: 3 },
  { action: 'flush_telemetry', traceId: 'tr_8910' }
];

const batch = engine.submitBatch('node_0', 1, txs);
if (!batch || !batch.batchId) throw new Error('Batch creation failed');
console.log('✓ Test 1: Submitted transaction batch with 3 actions (batchId: ' + batch.batchId.slice(0, 12) + '...)');

// Test 2: Form Certificate of Availability (CoA) with quorum 2f+1=3
const coa = engine.collectSignaturesAndFormCoA(batch.batchId);
const signerCount = Object.keys(coa.signatures).length;
if (signerCount !== 3) throw new Error('Expected 3 signatures for CoA, got ' + signerCount);
console.log('✓ Test 2: Formed Certificate of Availability (CoA) with 2f+1=3 signers');

// Test 3: Retrieve available payload via CoA
const retrievedTxs = engine.getAvailableTransactions(coa.certificateId);
if (!retrievedTxs || retrievedTxs.length !== 3) throw new Error('Failed to retrieve transactions via CoA');
console.log('✓ Test 3: Reliably retrieved available transaction payload from CoA');

// Test 4: Write verification report
const report = {
  experiment: 'narwhal_mempool_engine',
  phase: 399,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  quorum: 3,
  batchId: batch.batchId,
  certificateId: coa.certificateId,
  signers: Object.keys(coa.signatures),
  retrievedTransactionCount: retrievedTxs.length,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_NARWHAL_MEMPOOL_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_NARWHAL_MEMPOOL_REPORT.json');

console.log('All Narwhal Mempool Engine tests passed successfully!');
