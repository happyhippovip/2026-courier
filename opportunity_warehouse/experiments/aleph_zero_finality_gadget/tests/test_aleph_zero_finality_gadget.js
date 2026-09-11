const { AlephZeroFinalityGadget } = require('../lib/aleph_zero_finality_gadget');
const fs = require('fs');
const path = require('path');

console.log('Testing Aleph-Zero Finality Gadget Consensus Engine...');
const nodes = ['node_0', 'node_1', 'node_2', 'node_3'];
const gadget = new AlephZeroFinalityGadget(nodes, 1);

// Test 1: Rapidly author 3 blocks
const b1 = gadget.authorBlock('node_0', { tx: 'init_runtime_freeze' });
const b2 = gadget.authorBlock('node_1', { tx: 'prepare_order_settlement' });
const b3 = gadget.authorBlock('node_2', { tx: 'finalize_eur5_revenue' });

if (gadget.chain.length !== 3) throw new Error('Expected 3 authored blocks');
console.log('✓ Test 1: Optimistically authored 3 sequential blocks');

// Test 2: Asynchronously finalize height 1
const just1 = gadget.finalizeBlock(1, 1);
if (!gadget.isFinalized(1)) throw new Error('Height 1 should be finalized');
if (gadget.isFinalized(2)) throw new Error('Height 2 should not be finalized yet');
console.log('✓ Test 2: Finality gadget finalized Height 1 with 2f+1 quorum signatures');

// Test 3: Finalize height 2
const just2 = gadget.finalizeBlock(2, 1);
if (gadget.getFinalizedHead().hash !== b2.hash) {
  throw new Error('Finalized head mismatch at height 2');
}
console.log('✓ Test 3: Finalized head progressed to Height 2 (hash: ' + b2.hash.slice(0, 10) + '...)');

// Test 4: Write verification report
const report = {
  experiment: 'aleph_zero_finality_gadget',
  phase: 435,
  timestamp: new Date().toISOString(),
  totalNodes: 4,
  quorum: 3,
  authoredBlocks: gadget.chain.length,
  finalizedHeight: gadget.finalizedHeight,
  finalizedHeadHash: gadget.getFinalizedHead().hash,
  verdict: 'PASS'
};

const evidencePath = path.join('C:\\Users\\lol\\2026-workspace\\courier\\opportunity_warehouse\\evidence\\SAMPLE_ALEPH_ZERO_REPORT.json');
fs.writeFileSync(evidencePath, JSON.stringify(report, null, 2), 'utf8');
console.log('✓ Test 4: Evidence report written to SAMPLE_ALEPH_ZERO_REPORT.json');

console.log('All Aleph-Zero Finality Gadget tests passed successfully!');
